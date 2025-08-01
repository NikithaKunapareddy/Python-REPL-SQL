"""
Test script for the Travel Booking Agent
Run this to test the agent functionality
"""

from agent_repl import TravelBookingAgent

def test_agent():
    """Test the agent with various natural language commands"""
    agent = TravelBookingAgent()
    
    print("🧪 Testing Travel Booking Agent with REPL Execution")
    print("=" * 60)
    
    # Test commands
    test_commands = [
        ("show booking 1", "Should fetch booking ID 1"),
        ("total price for user nikitha", "Should get all bookings for nikitha"),
        ("explain booking for id 2", "Should explain booking ID 2"),
        ("show bookings 1, 2, 3", "Should show multiple bookings"),
        ("find all bookings john", "Should find all bookings for john"),
        ("help", "Should show help text"),
    ]
    
    for command, description in test_commands:
        print(f"\n🔍 Test: {command}")
        print(f"📝 Expected: {description}")
        print("🤖 Agent Response:")
        print("-" * 40)
        
        try:
            result = agent.process_command(command, 'local')
            print(f"✅ Result: {result}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)

if __name__ == "__main__":
    test_agent()
