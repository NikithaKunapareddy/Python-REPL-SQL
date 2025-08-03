from agent_repl import TravelBookingAgent

agent = TravelBookingAgent()

test_phrases = [
    "provide all my bookings",
    "provide all bookings",
    "all my bookings", 
    "show my bookings",
    "show bookings for nikitha",
    "all bookings for nikitha"
]

print("Testing pattern matching:")
print("=" * 50)

for phrase in test_phrases:
    intent, params = agent.parse_natural_language(phrase)
    print(f"'{phrase}' -> Intent: {intent}, Params: {params}")

print("\n" + "=" * 50)
print("Testing actual execution:")

# Test the new provide all bookings pattern
print("\nExecuting: 'provide all my bookings'")
try:
    result = agent.process_command('provide all my bookings', 'local')
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 30)
print("Testing: 'provide all bookings'")
try:
    result = agent.process_command('provide all bookings', 'local')
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
