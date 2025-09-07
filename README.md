# KrishiMitra 

KrishiMitra is a comprehensive agricultural management system that leverages multiple AI agents to provide farmers with intelligent insights and support for their farming operations.

## Project Overview

KrishiMitra consists of two main components:

### Backend (Django)

A sophisticated multi-agent system built with Django that provides various agricultural services:

- **Farm Orchestrator**: Coordinates between different agricultural agents
- **Weather Agent**: Provides weather forecasts and alerts
- **Soil Agent**: Analyzes soil conditions and provides recommendations
- **Pest Agent**: Monitors and suggests pest control measures
- **Market Agent**: Tracks agricultural market prices and trends
- **Satellite Agent**: Processes satellite imagery for crop monitoring
- **Search Agent**: Handles information retrieval tasks
- **Notification Agent**: Manages user alerts and communications

### Frontend (Next.js)

A modern, responsive web interface built with:

- Next.js
- TypeScript
- Tailwind CSS
- Shadcn UI components

## Tech Stack

### Backend

- Python
- Django
- SQLite Database
- AI/ML Libraries (as required by agents)

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- Various UI components (Accordion, Cards, Charts, etc.)

## Project Structure

```
├── backend/
│   ├── backend/          # Django project settings
│   ├── home/            # Main Django app
│   │   └── agents/      # AI agent implementations
│   ├── manage.py
│   └── requirements.txt
│
└── frontend/
    ├── app/             # Next.js pages and routes
    ├── components/      # Reusable UI components
    ├── hooks/           # Custom React hooks
    └── lib/             # Utility functions
```

## Getting Started

### Backend Setup

1. Navigate to the backend directory:

   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations:

   ```bash
   python manage.py migrate
   ```

5. Start the Django server:
   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

## Features

- Real-time agricultural monitoring and insights
- Weather forecasting and alerts
- Soil health analysis and recommendations
- Pest detection and control suggestions
- Market price analysis and predictions
- Satellite imagery analysis
- User notifications and alerts
- Modern, responsive user interface

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
