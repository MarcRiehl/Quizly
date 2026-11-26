# Quizly

![Quizly Logo](assets/logo/logo-quizly.png)

Quizly is a Django REST Framework application that allows users to
create quizzes based on YouTube videos. After a user submits a YouTube
URL, the application downloads the audio track with **yt-dlp**,
transcribes it with **OpenAI Whisper**, and uses the **Google Gemini
API** to generate a quiz from the transcript. Each quiz contains ten
questions with four answer options each, exactly one of which is
correct.

Users can register, log in, manage their own quizzes, update the title
and description of their quizzes, and delete quizzes they have created.

## Features

-   User registration and authentication
-   Authentication using JWT access and refresh tokens stored in
    HTTP-only cookies
-   Create quizzes from YouTube URLs
-   Audio download with yt-dlp and transcription with OpenAI Whisper
-   AI-powered question generation using the Google Gemini API
-   Ten questions per generated quiz, each with four answer options and
    exactly one correct answer
-   Retrieve and delete personal quizzes; update their title and
    description
-   User-specific access control: users can only access and manage their
    own quizzes

## Technologies

-   Python
-   Django
-   Django REST Framework
-   Simple JWT (HTTP-only cookie authentication)
-   SQLite
-   yt-dlp
-   OpenAI Whisper
-   Google Gemini API
-   FFmpeg

## Prerequisites

Before installing Quizly, make sure the following tools are installed:

-   **Python**: [Download Python](https://www.python.org/downloads/)
-   **Git**: [Download Git](https://git-scm.com/downloads)
-   **FFmpeg**: Required by yt-dlp and Whisper for audio processing
-   **Google Gemini API key**: Required for AI-powered quiz generation

## Installation

### 1. Install Python and Git

#### Windows

1.  Download and install Python from
    [python.org](https://www.python.org/downloads/).
2.  During installation, enable **Add Python to PATH**.
3.  Download and install Git from
    [git-scm.com](https://git-scm.com/downloads).
4.  Open a new terminal and verify the installations:

``` powershell
python --version
git --version
```

#### macOS

1.  Install Python from [python.org](https://www.python.org/downloads/)
    or use Homebrew.
2.  Install Git. If you have Xcode Command Line Tools installed, Git may
    already be available.
3.  Verify the installations:

``` bash
python3 --version
git --version
```

#### Linux (Debian/Ubuntu)

``` bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
python3 --version
git --version
```

### 2. Clone the repository

Open a terminal and clone the repository:

``` bash
git clone https://github.com/MarcRiehl/Quizly.git
cd quizly_app
```

### 3. Create and activate a virtual environment

A virtual environment keeps the project's Python dependencies separate
from other projects.

#### Windows (PowerShell or cmd)

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

If you are using Git Bash on Windows, activate the environment with
`source .venv/Scripts/activate` instead.

#### macOS / Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install the dependencies

With the virtual environment activated, install the required packages:

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Install FFmpeg

FFmpeg must be installed and available in your system PATH.

#### Windows: Download

1.  Open the [FFmpeg download page](https://ffmpeg.org/download.html).
2.  Download a current Windows build (for example, a build provided by
    gyan.dev or BtbN).
3.  Extract the archive, for example to `C:\ffmpeg`.
4.  Add the `bin` directory (for example, `C:\ffmpeg\bin`) to your
    Windows PATH environment variable.
5.  Open a new terminal and check the installation:

``` powershell
ffmpeg -version
```

#### Windows: Using winget

Alternatively, install FFmpeg from the terminal:

``` powershell
winget install --id Gyan.FFmpeg -e --source winget
```

#### macOS: Using Homebrew

If Homebrew is not installed yet, follow the instructions at
[brew.sh](https://brew.sh/). Then install FFmpeg:

``` bash
brew install ffmpeg
```

#### Linux (Debian/Ubuntu)

``` bash
sudo apt install ffmpeg
```

Verify the installation:

``` bash
ffmpeg -version
```

### 6. Get a Google Gemini API key

Quizly uses Google's Gemini API to generate quiz questions.

1.  Open [Google AI Studio](https://aistudio.google.com/apikey).
2.  Sign in with your Google account.
3.  Create an API key.
4.  Add the key to your local `.env` file in the next step.

See the [Gemini API
documentation](https://ai.google.dev/gemini-api/docs/libraries) for
further information.

### 7. Configure environment variables

Copy `.env.example` to a new file named `.env` in the project's root
directory:

``` bash
cp .env.example .env
```

On Windows (PowerShell), use `Copy-Item .env.example .env` instead.

The file contains the following variables:

``` env
SECRET_KEY='Add a "Secret key" in the .env file.'
GEMINI_API_KEY='Add your Gemini API key here.'
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODELS=gemini-3.7-flash,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite
```

Replace the `SECRET_KEY` placeholder with a secure Django secret key.
You can generate one with:

``` bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Then add your Gemini API key to `GEMINI_API_KEY`.

`GEMINI_MODEL` is the model used for quiz generation. If it is
unavailable (for example, overloaded or rate-limited), the models in
`GEMINI_FALLBACK_MODELS` are tried in the given order.

**Important:** Never commit your `.env` file or expose your secret key
or API key. Make sure `.env` is listed in `.gitignore`.

### 8. Apply database migrations

Run the database migrations:

``` bash
python manage.py migrate
```

### 9. Create an administrator (optional)

To access the Django administration interface, create a superuser:

``` bash
python manage.py createsuperuser
```

Follow the prompts in the terminal.

### 10. Start the development server

Run the local Django development server:

``` bash
python manage.py runserver
```

The API is now available at:

``` text
http://127.0.0.1:8000/
```

Stop the server with `Ctrl + C`.

## API Endpoints

All API endpoints use the `/api/` prefix.

| Method | Endpoint              | Description                                                                                       | Permissions                                        |
| ------ | --------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| POST   | `/api/register/`      | Registers a new user.                                                                             | None                                               |
| POST   | `/api/login/`         | Logs in a user and sets authentication cookies.                                                   | None                                               |
| POST   | `/api/logout/`        | Logs out the user and deletes all tokens.                                                         | Authentication required                            |
| POST   | `/api/token/refresh/` | Renews the access token using the refresh token.                                                  | Authentication via `refresh_token` cookie required |
| POST   | `/api/quizzes/`       | Creates a new quiz based on a YouTube URL.                                                        | Authentication required                            |
| GET    | `/api/quizzes/`       | Retrieves all quizzes belonging to the authenticated user.                                        | Authentication required                            |
| GET    | `/api/quizzes/{id}/`  | Retrieves a specific quiz. Users can only access their own quizzes.                               | Authentication required – Owner only               |
| PATCH  | `/api/quizzes/{id}/`  | Partially updates a quiz (only `title` and `description`). Users can only edit their own quizzes. | Authentication required – Owner only               |
| DELETE | `/api/quizzes/{id}/`  | Deletes a quiz. Users can only delete their own quizzes.                                          | Authentication required – Owner only               |

## Authentication

The login endpoint sets the `access_token` and `refresh_token` cookies
as HTTP-only cookies. The logout endpoint requires an authenticated
request, blacklists the refresh tokens, and removes both cookies. The
token refresh endpoint uses the `refresh_token` cookie to obtain a
renewed access token.

Make sure your frontend sends cookies with API requests (for example,
`credentials: "include"` with `fetch`).

## Frontend

The backend accepts cross-origin requests (CORS) only from the following
frontend origins:

-   `http://127.0.0.1:5500`
-   `http://localhost:5500`

Serve the frontend from one of these origins, for example with the VS
Code Live Server extension.

## Project Notes

-   Each authenticated user can only retrieve, update, or delete their
    own quizzes.
-   Quiz generation requires a valid Google Gemini API key.
-   FFmpeg must be installed and accessible through the system PATH.
-   On the first quiz generation, Whisper downloads its speech
    recognition model (`base`, about 140 MB). This happens only once.
-   Creating a quiz can take several minutes, depending on the length of
    the video, because the audio is downloaded and transcribed locally
    before the quiz is generated.
-   Keep local secrets in `.env`; do not add credentials to the
    repository.

## License

This project was created exclusively as part of the Developer Akademie training program. It is intended for educational and demonstration purposes only and is not licensed for free use, distribution, modification, or redistribution without prior permission from the author.
