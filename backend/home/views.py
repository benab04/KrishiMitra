from django.http import StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import traceback
import time
import threading
from queue import Queue
from typing import Optional

from home.agents.farm_orchestrator import FarmOrchestratorAgent


class SSEProgressTracker:
    """Handles progress tracking and message queuing for SSE"""
    
    def __init__(self):
        self.message_queue = Queue()
        self.is_active = True
        self.last_activity = time.time()
    
    def add_message(self, message: str, event_type: str = "progress"):
        """Add a message to the queue"""
        if self.is_active:
            self.last_activity = time.time()
            self.message_queue.put({
                'message': message,
                'event': event_type,
                'timestamp': time.time()
            })
    
    def get_messages(self):
        """Generator that yields messages from the queue"""
        while self.is_active or not self.message_queue.empty():
            try:
                if not self.message_queue.empty():
                    msg_data = self.message_queue.get(timeout=1)
                    yield msg_data
                else:
                    # Check for timeout (no activity for 60 seconds)
                    if time.time() - self.last_activity > 60:
                        self.is_active = False
                        yield {
                            'message': 'Request timed out due to inactivity',
                            'event': 'timeout',
                            'timestamp': time.time()
                        }
                        break
                    time.sleep(0.1)
            except:
                break
    
    def stop(self):
        """Stop the progress tracker"""
        self.is_active = False


@csrf_exempt
def sse_query_farm_agents(request):
    """
    Enhanced SSE Endpoint with real-time progress updates and keep-alive messages
    """
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")

    if request.method != "POST":
        return StreamingHttpResponse(
            event_stream("Method not allowed", event="error"),
            content_type='text/event-stream',
            status=405
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
        print("Body----->",body)
        user_query = body.get("query")
        if not user_query:
            return StreamingHttpResponse(
                event_stream("Missing 'query' in request", event="error"),
                content_type='text/event-stream',
                status=400
            )

        # Create progress tracker
        progress_tracker = SSEProgressTracker()
        
        def progress_callback(message: str, event_type: str):
            """Callback function for progress updates"""
            progress_tracker.add_message(message, event_type)

        def stream():
            try:
                # Send initial connection confirmation
                yield event_stream("Connection established", event="connected")
                yield event_stream("Initializing Farm AI Assistant...", event="status")
                
                # Create orchestrator with progress callback
                orchestrator = FarmOrchestratorAgent(progress_callback=progress_callback)
                if not orchestrator:
                    progress_tracker.add_message("Failed to create orchestrator", "error")
                    return

                test_context = {
                    "user_id": None,  # Safe mode - no DB operations
                    "farm_id": 1,
                    "farm_location": "California",
                    "farm_name": "Test Farm"
                }

                # Start processing in a separate thread
                result_container = {"result": None, "error": None}
                
                def process_query():
                    try:
                        result = orchestrator.process_query(user_query, test_context, progress_callback)
                        result_container["result"] = result
                        progress_tracker.add_message("Processing completed successfully!", "processing_complete")
                    except Exception as e:
                        result_container["error"] = e
                        progress_tracker.add_message(f"Processing failed: {str(e)}", "processing_error")
                    finally:
                        progress_tracker.stop()

                # Start processing thread
                processing_thread = threading.Thread(target=process_query)
                processing_thread.daemon = True
                processing_thread.start()

                # Stream progress updates
                for msg_data in progress_tracker.get_messages():
                    message = msg_data['message']
                    event_type = msg_data['event']
                    
                    # Send progress update
                    yield event_stream(message, event=event_type)
                    
                    # If processing is complete, break to send final results
                    if event_type in ['processing_complete', 'processing_error', 'timeout']:
                        break

                # Wait for processing to complete (with timeout)
                processing_thread.join(timeout=5)

                # Send final results
                if result_container["result"]:
                    result = result_container["result"]
                    
                    # Send metadata
                    agent_responses = result.get("agent_responses", {})
                    errors = {
                        agent: response.get("error") for agent, response in agent_responses.items()
                        if isinstance(response, dict) and "error" in response
                    }
                    successes = {
                        agent: response for agent, response in agent_responses.items()
                        if agent not in errors
                    }

                    yield event_stream(json.dumps({
                        "intent_classification": result.get("intent_classification"),
                        "agents_to_run": result.get("agents_to_run", []),
                        "agents_run": list(agent_responses.keys()),
                        "confidence_score": result.get("confidence_score", 0.0),
                        "success_count": len(successes),
                        "error_count": len(errors),
                        "errors": errors,
                    }), event="meta")

                    # Send individual agent results
                    for agent, response in agent_responses.items():
                        yield event_stream(json.dumps({
                            "agent": agent,
                            "response": response
                        }), event="agent_result")

                    # Send final response
                    final_response = result.get("final_response", "")
                    if final_response:
                        yield event_stream(final_response, event="final_response")
                    
                    # Send completion
                    yield event_stream("Query processing completed successfully!", event="complete")

                elif result_container["error"]:
                    error_msg = str(result_container["error"])
                    yield event_stream(f"Processing failed: {error_msg}", event="error")
                    yield event_stream(traceback.format_exc(), event="trace")
                
                else:
                    yield event_stream("Processing timed out or was interrupted", event="timeout")

            except Exception as e:
                yield event_stream(f"Fatal error in stream: {str(e)}", event="error")
                yield event_stream(traceback.format_exc(), event="trace")
            finally:
                # Ensure cleanup
                progress_tracker.stop()

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        
        # Set SSE headers
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Cache-Control'
        
        return response

    except Exception as e:
        return StreamingHttpResponse(
            event_stream(f"Fatal initialization error: {str(e)}", event="error"),
            content_type='text/event-stream',
            status=500
        )


def event_stream(data, event=None):
    """
    Format data as an SSE event with proper escaping.
    """
    msg = ""
    if event:
        msg += f"event: {event}\n"
    
    # Handle both string and dict/list data
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data)
    else:
        data_str = str(data)
    
    # Properly format multi-line data
    for line in data_str.splitlines():
        msg += f"data: {line}\n"
    
    # Add empty line to complete the event
    msg += "\n"
    return msg


# Alternative simpler endpoint without threading (if you face threading issues)
@csrf_exempt 
def sse_query_farm_agents_simple(request):
    """
    Simplified SSE endpoint without threading - processes synchronously but with progress updates
    """
     # Handle CORS preflight request
    if request.method == "OPTIONS":
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Cache-Control'
        response['Access-Control-Max-Age'] = '86400'
        return response
    
    if request.method != "POST":
        return StreamingHttpResponse(
            event_stream("Method not allowed", event="error"),
            content_type='text/event-stream',
            status=405
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
        user_query = body.get("query")
        if not user_query:
            return StreamingHttpResponse(
                event_stream("Missing 'query' in request", event="error"),
                content_type='text/event-stream',
                status=400
            )

        def stream():
            messages_sent = []  # Track sent messages to avoid duplicates
            last_keep_alive = time.time()
            
            def progress_callback(message: str, event_type: str):
                """Immediate progress callback that yields directly"""
                nonlocal last_keep_alive
                last_keep_alive = time.time()
                
                # Avoid duplicate messages
                msg_key = f"{event_type}:{message}"
                if msg_key not in messages_sent:
                    messages_sent.append(msg_key)
                    return event_stream(message, event=event_type)
                return ""

            try:
                # Send connection established
                yield event_stream("Connection established", event="connected")
                yield event_stream("Starting Farm AI Assistant...", event="status")
                
                # Create orchestrator
                orchestrator = FarmOrchestratorAgent()
                
                test_context = {
                    "user_id": None,
                    "farm_id": 1,
                    "farm_location": "California", 
                    "farm_name": "Test Farm"
                }

                # Process with progress updates
                start_time = time.time()
                result = None
                
                # Custom process method that yields progress
                def process_with_updates():
                    nonlocal result, last_keep_alive
                    
                    try:
                        # Send progress update
                        yield event_stream("🚀 Starting query processing...", event="progress")
                        
                        # Process the query (this will trigger progress callbacks through the orchestrator)
                        result = orchestrator.process_query(user_query, test_context, progress_callback)
                        
                        # Send periodic keep-alives during processing
                        current_time = time.time()
                        if current_time - last_keep_alive > 3:  # 3 seconds since last update
                            yield event_stream("Still processing...", event="keep_alive")
                            last_keep_alive = current_time
                            
                    except Exception as e:
                        yield event_stream(f"Processing error: {str(e)}", event="error")
                        raise

                # Process and stream updates
                for update in process_with_updates():
                    if update:  # Only yield non-empty updates
                        yield update

                # Send results if successful
                if result:
                    agent_responses = result.get("agent_responses", {})
                    errors = {
                        agent: response.get("error") for agent, response in agent_responses.items()
                        if isinstance(response, dict) and "error" in response
                    }
                    successes = {
                        agent: response for agent, response in agent_responses.items()
                        if agent not in errors
                    }

                    # Send metadata
                    yield event_stream(json.dumps({
                        "intent_classification": result.get("intent_classification"),
                        "agents_to_run": result.get("agents_to_run", []),
                        "agents_run": list(agent_responses.keys()),
                        "confidence_score": result.get("confidence_score", 0.0),
                        "success_count": len(successes),
                        "error_count": len(errors),
                        "errors": errors,
                        "processing_time": round(time.time() - start_time, 2)
                    }), event="meta")

                    # Send agent results
                    for agent, response in agent_responses.items():
                        yield event_stream(json.dumps({
                            "agent": agent,
                            "response": response
                        }), event="agent_result")

                    # Send final response
                    final_response = result.get("final_response", "")
                    if final_response:
                        yield event_stream(final_response, event="final_response")

                    yield event_stream("Processing completed successfully!", event="complete")
                else:
                    yield event_stream("No result generated", event="warning")

            except Exception as e:
                yield event_stream(f"Stream error: {str(e)}", event="error")
                yield event_stream(traceback.format_exc(), event="trace")

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        # response['Connection'] = 'keep-alive' 
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response

    except Exception as e:
        return StreamingHttpResponse(
            event_stream(f"Fatal error: {str(e)}", event="error"),
            content_type='text/event-stream',
            status=500
        )