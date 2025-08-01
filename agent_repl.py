import re
import subprocess
import sys
import os
from fetch_and_calculate import fetch_all_bookings_for_user, fetch_and_explain_booking

class TravelBookingAgent:
    """
    Agent that interprets natural language commands and executes 
    booking functions via REPL-style ex📋 SINGLE BOOKING:
• "show booking 1" - Get detailed breakdown for booking ID 1
• "explain booking 2" - Show price calculation for booking ID 2

🔍 CHECK BOOKING OWNER:
• "who owns booking 1" - See which user booked booking ID 1
• "which user has booking 2" - Check owner of booking ID 2

�️ VIEW ALL BOOKINGS:
• "show all bookings" - See every booking in the system
• "list all bookings" - See all bookings with users and routes

�📊 ALL USER BOOKINGS:
• "show me all bookings under nikitha" - All bookings with full details
• "find bookings of john" - All bookings with full details

💰 USER TOTALS (Summary Only):
• "total price for user nikitha" - Route-wise summary + grand total

🔢 MULTIPLE SPECIFIC BOOKINGS:
• "show bookings 1, 2, 3" - Sum of specific booking IDs"""
    
    def __init__(self):
        self.commands = {
            'booking_by_id': r'(?:show|explain|calculate|get)\s+(?:booking|price)\s+(?:for\s+)?(?:id\s+)?(\d+)',
            'booking_by_user': r'(?:show|get|find)\s+(?:me\s+)?(?:all\s+)?bookings?\s+(?:for|under|of)\s+(?:user\s+)?["\']?(\w+)["\']?',
            'user_total': r'(?:total|sum)\s+(?:price|cost)\s+(?:for|of|under)\s+(?:user\s+)?["\']?(\w+)["\']?',
            'multiple_bookings': r'(?:show|explain)\s+bookings?\s+(\d+(?:\s*,\s*\d+)*)',
            'booking_owner': r'(?:who|which\s+user|owner)\s+(?:owns|has|booked)\s+booking\s+(\d+)',
            'all_bookings': r'(?:show|list)\s+(?:all\s+)?(?:bookings?|system\s+bookings?)',
            'help': r'(?:help|what\s+can\s+you\s+do|commands)',
        }
    
    def parse_natural_language(self, user_input):
        """Parse natural language input and extract intent and parameters"""
        original_input = user_input.strip()
        user_input_lower = user_input.lower().strip()
        
        for intent, pattern in self.commands.items():
            # Use lowercase for pattern matching
            match = re.search(pattern, user_input_lower)
            if match:
                # But extract parameters from original input to preserve case
                if intent in ['booking_by_user', 'user_total']:
                    # For user commands, extract username with original case
                    original_match = re.search(pattern, original_input, re.IGNORECASE)
                    if original_match:
                        return intent, original_match.groups()
                return intent, match.groups()
        
        return None, None
    
    def execute_in_repl(self, code_to_execute):
        """Execute Python code in a REPL-like environment"""
        try:
            # Create a local namespace with our functions
            local_namespace = {
                'fetch_all_bookings_for_user': fetch_all_bookings_for_user,
                'fetch_and_explain_booking': fetch_and_explain_booking,
            }
            
            print(f"🤖 Agent executing in LOCAL REPL: {code_to_execute}")
            print("=" * 60)
            
            # Execute the code in REPL-style using exec for multi-line code
            exec(code_to_execute, {"__builtins__": __builtins__}, local_namespace)
            
            # Get the result from the local namespace
            result = local_namespace.get('result', None)
            
            print("=" * 60)
            print(f"✅ LOCAL REPL execution completed. Result: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Error in LOCAL REPL execution: {e}")
            return None
    
    def execute_system_repl(self, code_to_execute):
        """Execute code in actual Python REPL subprocess"""
        try:
            print(f"🤖 Agent executing in SYSTEM REPL: {code_to_execute}")
            print("=" * 60)
            
            # Prepare the code with imports
            full_code = f"""
import sys
import os
sys.path.append(os.getcwd())
from fetch_and_calculate import fetch_all_bookings_for_user, fetch_and_explain_booking

# Execute the agent command
result = {code_to_execute}
print("\\n" + "="*50)
print(f"🔥 SYSTEM REPL RESULT: {{result}}")
print("="*50)
"""
            
            # Execute in subprocess (actual REPL call)
            process = subprocess.run(
                [sys.executable, '-c', full_code],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            
            print(process.stdout)
            if process.stderr:
                print(f"🚨 REPL Errors: {process.stderr}")
            
            # Extract result from output
            lines = process.stdout.split('\n')
            for line in lines:
                if 'SYSTEM REPL RESULT:' in line:
                    result = line.split('SYSTEM REPL RESULT: ')[1]
                    print(f"✅ SYSTEM REPL execution completed. Final result: {result}")
                    return result
                    
            print("✅ SYSTEM REPL execution completed")
            return "Execution completed"
            
        except Exception as e:
            print(f"❌ Error in SYSTEM REPL: {e}")
            return None
    
    def execute_interactive_repl(self, code_to_execute):
        """Execute code by launching interactive Python REPL"""
        try:
            print(f"🤖 Agent launching INTERACTIVE REPL for: {code_to_execute}")
            print("=" * 60)
            
            # Create a temporary script
            script_content = f"""
# Auto-generated by Travel Booking Agent
import sys
import os
sys.path.append(os.getcwd())
from fetch_and_calculate import fetch_all_bookings_for_user, fetch_and_explain_booking

print("🤖 Agent REPL Environment Loaded!")
print("Available functions:")
print("- fetch_all_bookings_for_user(username)")
print("- fetch_and_explain_booking(booking_id)")
print("\\nExecuting agent command: {code_to_execute}")
print("=" * 50)

# Execute the agent command
result = {code_to_execute}

print("=" * 50)
print(f"🎯 Agent execution result: {{result}}")
print("\\nType exit() to leave REPL")

# Drop into interactive mode
import code
code.interact(local=locals())
"""
            
            # Write to temp file and execute
            with open('agent_repl_session.py', 'w') as f:
                f.write(script_content)
            
            # Launch interactive Python
            os.system(f'{sys.executable} -i agent_repl_session.py')
            
            # Clean up
            if os.path.exists('agent_repl_session.py'):
                os.remove('agent_repl_session.py')
                
            return "Interactive REPL session completed"
            
        except Exception as e:
            print(f"❌ Error in INTERACTIVE REPL: {e}")
            return None
    
    def process_command(self, user_input, repl_mode='local'):
        """Process natural language command and execute appropriate function"""
        intent, params = self.parse_natural_language(user_input)
        
        if intent is None:
            return "❓ I don't understand that command. Type 'help' for available commands."
        
        # Generate the appropriate Python code to execute
        code_to_execute = None
        
        if intent == 'booking_by_id':
            booking_id = params[0]
            code_to_execute = f"result = fetch_and_explain_booking({booking_id})"
            
        elif intent == 'booking_by_user':
            username = params[0]
            # EXACT case-sensitive search - shows only the exact username requested
            code_to_execute = f'''
import sqlite3
conn = sqlite3.connect("travel.db")
c = conn.cursor()

# Find users with EXACT username match (case sensitive)
c.execute("SELECT id, username FROM users WHERE username = ?", ("{username}",))
exact_users = c.fetchall()

if not exact_users:
    print(f"No users found with EXACT name '{username}' (case sensitive)")
    # Offer case-insensitive search as suggestion
    c.execute("SELECT id, username FROM users WHERE lower(username) = lower(?)", ("{username}",))
    similar_users = c.fetchall()
    if similar_users:
        similar_names = [user[1] for user in similar_users]
        print(f"� Did you mean one of these similar users? {{similar_names}}")
    result = 0.0
else:
    user_id, user_name = exact_users[0]
    print(f"\\n� Found EXACT user: {{user_name}} (ID: {{user_id}})")
    print("📋 SHOWING ALL BOOKINGS:")
    print("="*60)
    
    c.execute("SELECT id FROM bookings WHERE user_id=?", (user_id,))
    user_bookings = [row[0] for row in c.fetchall()]
    
    if not user_bookings:
        print(f"No bookings found for user '{{user_name}}'")
        result = 0.0
    else:
        from collections import defaultdict
        route_totals = defaultdict(float)
        user_total = 0.0
        
        for bid in sorted(user_bookings):
            price = fetch_and_explain_booking(bid)
            if price:
                # Get route info for this booking
                c.execute("""
                    SELECT r.origin, r.destination 
                    FROM bookings b 
                    JOIN routes r ON b.route_id = r.id 
                    WHERE b.id = ?
                """, (bid,))
                route_info = c.fetchone()
                if route_info:
                    route_key = f"{{route_info[0]}} -> {{route_info[1]}}"
                    route_totals[route_key] += price
                user_total += price
        
        # Show summary for this exact user
        print("\\n" + "="*50)
        print(f"📊 ROUTE-WISE SUMMARY FOR USER '{{user_name}}':")
        print("="*50)
        for route, total in route_totals.items():
            print(f"Route {{route}}: {{total}}")
        print("-"*30)
        print(f"🎯 TOTAL FOR {{user_name}}: {{user_total}}")
        print("="*50)
        
        result = user_total

conn.close()
'''
            
        elif intent == 'user_total':
            username = params[0]
            # Dynamic case-insensitive user search for totals - works for ANY username
            code_to_execute = f'''
import sqlite3
conn = sqlite3.connect("travel.db")
c = conn.cursor()

# Find all users with same name (case insensitive) - DYNAMIC for any username
c.execute("SELECT id, username FROM users WHERE lower(username) = lower(?)", ("{username}",))
matching_users = c.fetchall()

if not matching_users:
    print(f"No users found with name '{username}' (case insensitive)")
    result = 0.0
else:
    if len(matching_users) > 1:
        user_names = [user[1] for user in matching_users]
        print(f"\\n📊 CALCULATING TOTAL FOR ALL '{username.upper()}' USERS: {{user_names}}")
    else:
        user_name = matching_users[0][1]
        print(f"\\n📊 CALCULATING TOTAL FOR USER '{{user_name}}'...")
    
    all_booking_ids = []
    for user_id, user_name in matching_users:
        c.execute("SELECT id FROM bookings WHERE user_id=?", (user_id,))
        user_bookings = [row[0] for row in c.fetchall()]
        all_booking_ids.extend(user_bookings)
    
    if not all_booking_ids:
        print(f"No bookings found for user(s) with name '{username}'")
        result = 0.0
    else:
        from collections import defaultdict
        route_totals = defaultdict(float)
        grand_total = 0.0
        
        for bid in all_booking_ids:
            # Get price by calling fetch_and_explain_booking but suppress its output
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            try:
                price = fetch_and_explain_booking(bid)
            finally:
                sys.stdout = old_stdout
            
            if price:
                # Get route info for this booking
                c.execute("""
                    SELECT r.origin, r.destination 
                    FROM bookings b 
                    JOIN routes r ON b.route_id = r.id 
                    WHERE b.id = ?
                """, (bid,))
                route_info = c.fetchone()
                if route_info:
                    route_key = f"{{route_info[0]}} -> {{route_info[1]}}"
                    route_totals[route_key] += price
                grand_total += price
        
        print("\\n" + "="*50)
        if len(matching_users) > 1:
            print(f"📊 ROUTE-WISE SUMMARY FOR ALL '{username.upper()}' USERS:")
        else:
            print("📊 ROUTE-WISE SUMMARY:")
        print("="*50)
        for route, total in route_totals.items():
            print(f"Route {{route}}: {{total}}")
        print("-"*30)
        if len(matching_users) > 1:
            print(f"🎯 GRAND TOTAL FOR ALL '{username.upper()}': {{grand_total}}")
        else:
            print(f"🎯 GRAND TOTAL: {{grand_total}}")
        print("="*50)
        result = grand_total

conn.close()
result
'''
            
        elif intent == 'booking_owner':
            booking_id = params[0]
            code_to_execute = f'''
import sqlite3
conn = sqlite3.connect("travel.db")
c = conn.cursor()
c.execute("""
    SELECT u.username, b.id 
    FROM bookings b 
    JOIN users u ON b.user_id = u.id 
    WHERE b.id = ?
""", ({booking_id},))
result_row = c.fetchone()
if result_row:
    username, bid = result_row
    print(f"📍 Booking ID {{bid}} belongs to user: {{username}}")
    result = f"Booking {{bid}} → User: {{username}}"
else:
    print(f"❌ Booking ID {{booking_id}} not found")
    result = f"Booking {{booking_id}} not found"
conn.close()
result
'''
            
        elif intent == 'all_bookings':
            code_to_execute = f'''
import sqlite3
conn = sqlite3.connect("travel.db")
c = conn.cursor()
c.execute("""
    SELECT b.id, u.username, r.origin, r.destination
    FROM bookings b 
    JOIN users u ON b.user_id = u.id 
    JOIN routes r ON b.route_id = r.id
    ORDER BY b.id
""")
all_bookings = c.fetchall()
print("\\n📋 ALL BOOKINGS IN SYSTEM:")
print("="*60)
for bid, username, origin, dest in all_bookings:
    print(f"Booking {{bid:2}} → User: {{username:10}} → Route: {{origin}} -> {{dest}}")
print("="*60)
print(f"Total bookings in system: {{len(all_bookings)}}")
conn.close()
result = f"Found {{len(all_bookings)}} total bookings"
result
'''
            
        elif intent == 'multiple_bookings':
            booking_ids = [id.strip() for id in params[0].split(',')]
            # Create a simple loop for multiple bookings
            booking_ids_int = [int(bid) for bid in booking_ids if bid.isdigit()]
            code_to_execute = f"sum([fetch_and_explain_booking(bid) or 0 for bid in {booking_ids_int}])"
            
        elif intent == 'help':
            return self.show_help()
        
        if code_to_execute:
            # Execute based on REPL mode
            if repl_mode == 'system':
                return self.execute_system_repl(code_to_execute)
            elif repl_mode == 'interactive':
                return self.execute_interactive_repl(code_to_execute)
            else:  # local
                return self.execute_in_repl(code_to_execute)
        
        return "❓ Could not generate executable code for that command."
    
    def show_help(self):
        """Show available commands"""
        help_text = """
🤖 Travel Booking Agent - Simple Commands

📋 SINGLE BOOKING:
• "show booking 1" - Get detailed breakdown for booking ID 1
• "explain booking 2" - Show price calculation for booking ID 2

📊 ALL USER BOOKINGS:
• "show me all bookings under nikitha" - All bookings with full details
• "find bookings of john" - All bookings with full details

� USER TOTALS (Summary Only):
• "total price for user nikitha" - Route-wise summary + grand total

🔢 MULTIPLE SPECIFIC BOOKINGS:
• "show bookings 1, 2, 3" - Sum of specific booking IDs

🆘 OTHER:
• "help" - Show this help
• "quit" - Exit

💡 Use "show booking X" for single, "total price" for summary!
        """
        return help_text
    
    def chat_loop(self):
        """Simple chat loop for the agent"""
        print("🤖 Travel Booking Agent Started!")
        print("=" * 40)
        print("Type booking commands or 'help' for examples.")
        print("Type 'quit' to exit.")
        print("=" * 40)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break
                    
                elif user_input.lower() == '':
                    continue
                
                # Process the command (always use local REPL for simplicity)
                result = self.process_command(user_input, 'local')
                print(f"\n🤖 Result: {result}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")



if __name__ == "__main__":
    print("🚀 Travel Booking Agent")
    print("=" * 30)
    
    agent = TravelBookingAgent()
    print(agent.show_help())
    agent.chat_loop()
