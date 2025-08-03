@echo off
echo Starting Travel Booking Assistant...
echo.
echo Opening Streamlit app at http://localhost:8501
echo.
echo To stop the app, press Ctrl+C
echo.
streamlit run streamlit_app.py --server.port 8501 --server.headless false
pause
