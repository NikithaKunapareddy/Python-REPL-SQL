#!/usr/bin/env python3
"""
Launcher script for the Travel Booking Streamlit App
"""
import subprocess
import sys
import os

def main():
    print("🚀 Starting Travel Booking Assistant...")
    print("📱 Opening Streamlit app at http://localhost:8501")
    print("⏹️  To stop the app, press Ctrl+C")
    print("-" * 50)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.port", "8501",
            "--server.headless", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Thanks for using Travel Booking Assistant!")
    except Exception as e:
        print(f"❌ Error starting app: {e}")
        print("Make sure streamlit is installed: pip install streamlit")

if __name__ == "__main__":
    main()
