# Eksoterris

### Geospatial Platform for Lunar and Martian Analog Site Identification

<p align="center">
  <em>Exploring Earth's landscapes to support research on future Moon and Mars missions.</em>
</p>

---

## Overview

Eksoterris is a geospatial platform developed for the **NASA Space Apps Challenge 2026**. The project explores how environments on Earth can be compared with selected geological and environmental conditions found on the Moon and Mars.

Using scientific datasets, geospatial processing, 3D visualization, and Google's Gemini API, the platform helps identify and examine terrestrial locations that may serve as analogs for planetary exploration.

The goal is to bring these different sources of information together in an interactive environment where users can explore candidate locations and their characteristics.

## Features

- **Interactive 3D Globe:** Explore geographic locations through a 3D interface.
- **Analog Site Identification:** Investigate terrestrial environments based on selected lunar and Martian characteristics.
- **Geospatial Data Processing:** Organize and process geographic and scientific information for analysis.
- **Gemini API Integration:** Use Google's Gemini API to interpret available data and generate structured analysis.
- **Candidate Visualization:** View identified locations and their associated information through the platform.

## How It Works

The platform follows a workflow that connects scientific data, geospatial processing, and AI-based analysis.

1. **Data Collection:** Relevant planetary and terrestrial information is obtained from available scientific datasets and NASA resources.
2. **Data Preparation:** The collected information is organized and processed for use in the analysis.
3. **AI Analysis:** The Gemini API receives relevant information and helps generate structured responses based on the selected criteria.
4. **Location Identification:** Potential terrestrial analog sites are identified for further exploration.
5. **3D Visualization:** Candidate locations and their information are presented through the interactive interface.

## Technology Stack

| Area | Technologies |
|---|---|
| Programming Languages | Python, JavaScript |
| AI Integration | Google Gemini API |
| Backend | FastAPI, Uvicorn |
| Frontend | Vite, JavaScript |
| 3D Visualization | CesiumJS, Three.js |
| Scientific Data | NASA open data and geospatial resources |
| Package Management | npm, pip |

## Architecture

Eksoterris is divided into two main components.

### Frontend

- Provides the interactive user interface.
- Renders geographic information using 3D visualization.
- Displays candidate locations and analysis results.
- Communicates with the backend through API requests.

### Backend

- Handles scientific and geospatial data.
- Performs data preparation and processing.
- Integrates with the Gemini API.
- Exposes API endpoints consumed by the frontend.

## Project Structure

```text
Eksoterris/
│
├── backend/
│   ├── app.py
│   ├── data/
│   └── requirements.txt
│
├── docs/
├── public/
├── results/
├── src/
│
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── setup.ps1
├── start-backend.ps1
└── vite.config.js
```

## Getting Started

### Prerequisites

- Python
- Node.js and npm
- Google Gemini API key
- NASA API key, if required by the selected data sources

### 1. Clone the Repository

```bash
git clone https://github.com/JessicaLohaine/Eksoterris.git
cd Eksoterris
```

### 2. Configure Environment Variables

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Add the required API credentials to the corresponding variables.

> **Important:** Keep your API keys private. Never commit your `.env` file or expose secret credentials through frontend environment variables.

### 3. Install Dependencies

On Windows PowerShell, run:

```powershell
.\setup.ps1
```

This script sets up the Python virtual environment, installs the backend dependencies, and installs the frontend packages.

### 4. Start the Backend

```powershell
.\start-backend.ps1
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

### 5. Start the Frontend

Open another terminal in the project directory and run:

```bash
npm run dev
```

Vite will provide the local development URL.

## NASA Data and Resources

Eksoterris was developed as part of the **NASA Space Apps Challenge 2026**.

NASA scientific and geospatial resources contribute to the project's research, providing information used to explore similarities between terrestrial environments and selected conditions on the Moon and Mars.

Eksoterris is an independent project and is not affiliated with or endorsed by NASA.

## Limitations

Eksoterris is an experimental project intended for research and exploration.

The locations and interpretations produced by the platform should not be considered definitive scientific classifications. Results depend on the quality and availability of the underlying datasets, the selected comparison criteria, and the limitations of AI-generated analysis.

## Future Development

- Incorporating additional planetary and terrestrial datasets.
- Refining environmental comparison and scoring methods.
- Improving the traceability of scientific data.
- Expanding the platform's geospatial analysis capabilities.
- Developing additional validation methods for identified locations.

## Acknowledgements

Developed for the **NASA Space Apps Challenge 2026**.

The project brings together programming, geospatial technologies, scientific data, and artificial intelligence to explore terrestrial environments as references for planetary exploration.

---

<p align="center">
  <strong>Eksoterris</strong><br>
  <a href="https://github.com/JessicaLohaine/Eksoterris">GitHub Repository</a>
</p>
