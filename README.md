# CRITiQUE

> **A Student Review Platform Prototype (CS391 - Enterprenuership & Technology commercialization)**

CRITiQUE is a web-based platform designed to allow students to review and discover campus dining options. This prototype focuses on delivering a functional backend and a server-rendered user interface to facilitate reviews and recommendations.

## Project Structure

The repository is organized into two main directories:

* **`server/`**: The core application logic. It is a Python Flask app that uses server-rendered templates (Jinja2) and manages data with SQLite via SQLAlchemy.
* **`client/`**: Contains informational static pages (not currently used for the main application UI).

## Key Features

* **Review System**: Users can view and submit reviews for various campus dining locations.
* **Recommendation Engine**: Includes a `recommender.py` module to suggest options to users.
* **Server-Side Rendering**: Fast and efficient UI rendering without heavy client-side JavaScript.
* **Database**: Uses **SQLite** (`campuseats.db`) for lightweight and zero-configuration data storage.
* **Mock Authentication**: Simplified email-based login system for prototyping purposes.

## Tech Stack

* **Language**: Python 3.13
* **Framework**: Flask
* **Database**: SQLite & SQLAlchemy
* **Frontend**: HTML/CSS (Server-Rendered)

## Quick Start

Follow these steps to set up and run the server locally.

### Prerequisites
* Python 3.10 or higher
* pip (Python package manager)

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/Nishat-Ahmad/CRITiQUE.git](https://github.com/Nishat-Ahmad/CRITiQUE.git)
    cd CRITiQUE
    ```

2.  **Navigate to the server directory**
    ```bash
    cd server
    # OR if using PowerShell as per original instructions
    # Set-Location 'path\to\CRITiQUE\server'
    ```

3.  **Create and Activate a Virtual Environment**
    * *Windows (PowerShell):*
        ```powershell
        python -m venv .venv
        .\.venv\Scripts\Activate.ps1
        ```
    * *macOS/Linux:*
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

4.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Seed the Database (Optional but Recommended)**
    If you are running this for the first time, you may need to populate the database with initial data.
    ```bash
    python seed.py
    ```

6.  **Run the Application**
    ```bash
    python app.py
    ```

The server will start on `http://localhost:5000`. Open this URL in your browser to start using the app.

## Notes
* **Authentication**: The current auth system is mocked for demonstration. It uses email-based login but should be replaced with proper password hashing and token-based authentication (e.g., OAuth, JWT) for production use.
* **Database**: SQLite used.

## License
Distributed under the MIT License. See `LICENSE` for more information.
