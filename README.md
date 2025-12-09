# mpcs57200_final_project

This is a Streamlit-based web application that generates an adaptive quiz to test critical thinking and problem-solving skills. It uses OpenAI's GPT-4o model to create questions tailored to a specific topic or the content of an uploaded PDF file.

Features

Adaptive Difficulty: The quiz adjusts difficulty based on your performance (Elo rating system).

Two Question Modes: Randomly switches between Multiple Choice and detailed "Textbook Style" problems.

PDF Support: Upload any PDF to generate questions based specifically on its content.

Timer: A strict 2-minute timer per question to test fluency.

Analytics: Generates a personalized study plan and performance report at the end.

Prerequisites

Python 3.8 or higher

An OpenAI API Key (You can get one at platform.openai.com)

Installation

Clone or download this repository to your local machine.

Create a virtual environment (optional but recommended):

python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Configuration

Create a file named .env in the same folder as quiz_app.py.

Add your OpenAI API key to the file like this:

OPENAI_API_KEY=sk-proj-your-actual-api-key-here


(Alternatively, you can enter the key manually in the app sidebar every time you run it.)

Running the App

Run the application using Streamlit:

python -m streamlit run quiz_app.py


This will automatically open the app in your default web browser (usually at http://localhost:8501).

How to Use

Sidebar Setup:

If you didn't set the .env file, paste your API key in the sidebar.

Select Source Material:

Topic: Type any subject (e.g., "Quantum Mechanics", "19th Century Literature").

Upload PDF: Upload a document to be quizzed on its specific contents.

Adjust the Number of Questions.

Click Start Quiz.

Taking the Quiz:

Answer the question presented.

You have 2 minutes per question.

Use the Hint button if you are stuck (costs 50 points).

Results:

After finishing all questions, the app provides a detailed breakdown of your strengths, weaknesses, and a recommended study plan.