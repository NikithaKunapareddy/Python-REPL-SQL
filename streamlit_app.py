import streamlit as st
import sqlite3
import hashlib
import re
from datetime import datetime
from agent_repl import TravelBookingAgent
from booking import authenticate_user, get_route_info, calculate_final_price, book_ticket
from fetch_and_calculate import fetch_all_bookings_for_user, fetch_and_explain_booking
import sys
import io
from contextlib import contextmanager

# Page configuration
st.set_page_config(
    page_title="🚀 Travel Booking System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean CSS styling
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
    }
    
    .main {
        background-color: #ffffff;
        color: #333333;
        font-family: 'Segoe UI', sans-serif;
        padding: 1rem;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Simple styling */
    h1, h2, h3, h4 {
        color: #333333;
        font-family: 'Segoe UI', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

@contextmanager
def capture_stdout():
    """Context manager to capture stdout output"""
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    try:
        yield captured_output
    finally:
        sys.stdout = old_stdout

# Initialize session state
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "booking_context" not in st.session_state:
    st.session_state.booking_context = {}
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "current_user_id" not in st.session_state:
    st.session_state.current_user_id = None

# Chat-specific session state variables
if "chat_user_authenticated" not in st.session_state:
    st.session_state.chat_user_authenticated = False
if "chat_current_user" not in st.session_state:
    st.session_state.chat_current_user = None
if "chat_current_user_id" not in st.session_state:
    st.session_state.chat_current_user_id = None

# Initialize REPL agent
if "agent" not in st.session_state:
    try:
        from agent_repl import TravelBookingAgent
        st.session_state.agent = TravelBookingAgent()
    except ImportError:
        st.session_state.agent = None

# Initialize REPL output storage
if "repl_output" not in st.session_state:
    st.session_state.repl_output = []

# Simple booking functions
def authenticate_user(username, password):
    """Authenticate user login - creates new user if doesn't exist"""
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    # First check if user exists
    c.execute('SELECT id FROM users WHERE username=? AND password=?', (username, hashed))
    user = c.fetchone()
    
    if user:
        # User exists and password matches
        conn.close()
        return user[0]
    else:
        # Check if username exists but password is wrong
        c.execute('SELECT id FROM users WHERE username=?', (username,))
        existing_user = c.fetchone()
        
        if existing_user:
            # Username exists but wrong password
            conn.close()
            return None
        else:
            # User doesn't exist - create new user automatically
            try:
                c.execute('INSERT INTO users (username, password, loyalty_points) VALUES (?, ?, ?)', 
                         (username, hashed, 0))
                conn.commit()
                new_user_id = c.lastrowid
                conn.close()
                return new_user_id
            except Exception as e:
                print(f"Error creating user: {e}")
                conn.close()
                return None

def get_all_routes():
    """Get all available routes"""
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('SELECT id, origin, destination, departure_time, base_price, transport_type, seats_available FROM routes')
    routes = c.fetchall()
    conn.close()
    return routes

def add_route_suggestion(origin, destination):
    """Generate admin instructions for adding a new route"""
    return f"""
🔧 **Admin Instructions to Add Route:**

**SQL Command to add {origin} → {destination}:**
```sql
INSERT INTO routes (origin, destination, departure_time, base_price, transport_type, seats_available, seats_total) 
VALUES ('{origin}', '{destination}', '2025-01-15 10:00:00', 500.00, 'flight', 100, 100);
```

**Or use the admin panel to add:**
- Origin: {origin}
- Destination: {destination}  
- Price: $500 (adjust as needed)
- Transport: Flight/Bus/Train
- Seats: 100 (adjust as needed)
"""

def search_routes(origin=None, destination=None):
    """Search for routes between specific locations"""
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    
    if origin and destination:
        # Search for exact origin and destination
        c.execute('''SELECT id, origin, destination, departure_time, base_price, transport_type, seats_available 
                     FROM routes WHERE LOWER(origin) LIKE ? AND LOWER(destination) LIKE ?''', 
                  (f'%{origin.lower()}%', f'%{destination.lower()}%'))
    elif origin:
        # Search by origin only
        c.execute('''SELECT id, origin, destination, departure_time, base_price, transport_type, seats_available 
                     FROM routes WHERE LOWER(origin) LIKE ?''', (f'%{origin.lower()}%',))
    elif destination:
        # Search by destination only
        c.execute('''SELECT id, origin, destination, departure_time, base_price, transport_type, seats_available 
                     FROM routes WHERE LOWER(destination) LIKE ?''', (f'%{destination.lower()}%',))
    else:
        # Get all routes
        c.execute('SELECT id, origin, destination, departure_time, base_price, transport_type, seats_available FROM routes')
    
    routes = c.fetchall()
    conn.close()
    return routes

def extract_locations_from_message(message):
    """Extract origin and destination from user message"""
    # Common patterns for booking requests
    patterns = [
        r'book.*?from\s+(\w+).*?to\s+(\w+)',
        r'book.*?(\w+)\s+to\s+(\w+)',
        r'ticket.*?from\s+(\w+).*?to\s+(\w+)',
        r'travel.*?from\s+(\w+).*?to\s+(\w+)',
        r'(\w+)\s+to\s+(\w+)',
        r'from\s+(\w+).*?to\s+(\w+)'
    ]
    
    import re
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            return match.group(1), match.group(2)
    
    return None, None

def calculate_final_price(base_price, traveller_type='adult', user_id=None):
    """Calculate final price with discounts"""
    price = base_price
    # Apply child discount
    if traveller_type == 'child':
        price *= 0.5
    # Apply best discount from discounts table
    if user_id is not None:
        conn = sqlite3.connect('travel.db')
        c = conn.cursor()
        # Get user loyalty points
        c.execute('SELECT loyalty_points FROM users WHERE id=?', (user_id,))
        user_row = c.fetchone()
        loyalty_points = user_row[0] if user_row else 0
        # Find best discount
        c.execute('''SELECT percentage FROM discounts WHERE (user_type=? OR user_type IS NULL OR user_type='') AND min_points<=? ORDER BY percentage DESC LIMIT 1''', (traveller_type, loyalty_points))
        discount_row = c.fetchone()
        if discount_row:
            discount = discount_row[0]
            price *= (1 - discount / 100)
        conn.close()
    return round(price, 2)

def book_ticket(user_id, route_id, seat_number=None, traveller_type='adult'):
    """Book a ticket"""
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('SELECT seats_available, base_price, seats_total FROM routes WHERE id=?', (route_id,))
    route = c.fetchone()
    if not route or route[0] <= 0:
        conn.close()
        return {'error': 'No seats available'}
    seats_left, base_price, seats_total = route
    demand_factor = 1 + (1 - seats_left / seats_total) * 0.5
    price_paid = round(base_price * demand_factor, 2)
    final_price = calculate_final_price(price_paid, traveller_type, user_id)
    booking_time = datetime.now().isoformat()
    c.execute('INSERT INTO bookings (user_id, route_id, seat_number, price_paid, booking_time, status) VALUES (?, ?, ?, ?, ?, ?)',
              (user_id, route_id, seat_number, final_price, booking_time, 'confirmed'))
    c.execute('UPDATE routes SET seats_available = seats_available - 1 WHERE id=?', (route_id,))
    conn.commit()
    booking_id = c.lastrowid
    conn.close()
    return {'booking_id': booking_id, 'price_paid': final_price, 'status': 'confirmed'}

# Chat Booking Interface
def chat_booking_interface():
    """Simple chat-based booking interface"""
    st.title("🤖 Travel Booking Chatbot")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("← Back to Main Menu"):
            st.session_state.app_mode = "main_menu"
            st.rerun()
    
    # Initialize chat if empty
    if not st.session_state.chat_messages:
        welcome_msg = "Hello! I'm your travel booking assistant. I can help you book tickets, check routes, and get pricing information. How can I help you today?"
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome_msg})
    
    # Chat display
    st.subheader("Chat")
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
    
    # Chat input
    user_input = st.chat_input("Type your message here...")
    
    if user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Process and get response
        response = process_booking_chat(user_input)
        
        # Add assistant response
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        
        st.rerun()
    
    # Sidebar with user info and quick actions
    with st.sidebar:
        st.header("Chat Options")
        
        # Login status
        if st.session_state.chat_user_authenticated:
            st.success(f"Logged in as: {st.session_state.chat_current_user}")
            if st.button("Logout"):
                st.session_state.chat_user_authenticated = False
                st.session_state.chat_current_user = None
                st.session_state.chat_current_user_id = None
                st.session_state.booking_context = {}
                st.rerun()
        else:
            st.info("Login to book tickets")
        
        st.divider()
        
        # Quick actions
        st.subheader("Quick Actions")
        if st.button("Show All Routes"):
            st.session_state.chat_messages.append({"role": "user", "content": "show routes"})
            response = process_booking_chat("show routes")
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            st.rerun()
        
        if st.button("Help"):
            st.session_state.chat_messages.append({"role": "user", "content": "help"})
            response = process_booking_chat("help")
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            st.rerun()
        
        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.session_state.booking_context = {}
            st.rerun()

def process_booking_chat(message):
    """Process chat messages for complete booking flow"""
    message = message.lower().strip()
    
    # PRIORITY 1: Handle guided login process (must be first!)
    if st.session_state.booking_context.get('step') == 'asking_username':
        # User provided username, now ask for password
        username = message.strip()
        travel_intent = st.session_state.booking_context.get('travel_intent')  # Preserve travel intent
        st.session_state.booking_context = {
            'step': 'asking_password', 
            'username': username,
            'travel_intent': travel_intent  # Keep the original travel request
        }
        return f"✅ Got it! Username: **{username}**\n\n🔑 **Now, what's your password?**\n\nDon't worry, I'll securely check your credentials."
    
    # PRIORITY 2: Handle password input
    if st.session_state.booking_context.get('step') == 'asking_password':
        password = message.strip()
        username = st.session_state.booking_context.get('username')
        travel_intent = st.session_state.booking_context.get('travel_intent')
        
        # Check if user exists first
        conn = sqlite3.connect('travel.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username=?', (username,))
        existing_user = c.fetchone()
        conn.close()
        
        # Authenticate (this will create user if needed)
        user_id = authenticate_user(username, password)
        if user_id:
            st.session_state.chat_user_authenticated = True
            st.session_state.chat_current_user = username
            st.session_state.chat_current_user_id = user_id
            
            # Determine if this is a new user or existing user
            welcome_message = ""
            if not existing_user:
                welcome_message = f"🎉 **Welcome to the Travel Booking System, {username}!** 🆕\n\n✨ **New account created successfully!** You now have:\n• 0 loyalty points (earn more by booking trips!)\n• Access to all available discounts\n• Secure account with encrypted password\n\n"
            else:
                welcome_message = f"🎉 **Welcome back, {username}!** You're now logged in.\n\n"
            
            # After successful login, always ask for origin first
            st.session_state.booking_context = {'step': 'asking_origin'}
            return welcome_message + f"🌍 **Great! Now let's plan your trip!**\n\n🏠 **Where will you be traveling from?**\nPlease tell me your origin city (starting point):\n\nFor example:\n• 'Delhi'\n• 'Mumbai' \n• 'Vijayawada'\n• 'Chennai'\n\nWhat's your starting city?"
        else:
            st.session_state.booking_context = {
                'step': 'asking_username',
                'travel_intent': travel_intent  # Preserve travel intent on retry
            }
            return f"❌ Sorry, I couldn't log you in with those credentials.\n\n🔄 Let's try again! What's your **username**?"
    
    # PRIORITY 3: Handle route selection (must be before general booking logic)
    if st.session_state.booking_context.get('step') == 'route_selection':
        if message.isdigit():
            route_num = int(message)
            available_routes = st.session_state.booking_context.get('available_routes', [])
            if 1 <= route_num <= len(available_routes):
                selected_route = available_routes[route_num - 1]
                st.session_state.booking_context = {
                    'step': 'traveller_type',
                    'route': selected_route
                }
                return f"🎫 Great! You selected:\n{selected_route[1]} → {selected_route[2]} ({selected_route[5]})\nPrice: ${selected_route[4]:.2f}\n\nPlease choose traveller type:\n- Type 'adult' for adult ticket\n- Type 'child' for child ticket (50% discount)"
            else:
                return f"❌ Invalid route number. Please choose between 1 and {len(available_routes)}."
    
    # PRIORITY 3.5: Handle direct numeric input for route selection (when user types just a number)
    # BUT ONLY if not in a specific step that expects numeric input
    if (message.isdigit() and st.session_state.chat_user_authenticated and 
        st.session_state.booking_context.get('step') not in ['new_route_price', 'new_route_seats', 'discount_selection']):
        route_num = int(message)
        
        # Check if we're in offer_new_route step (user selecting from available routes)
        if st.session_state.booking_context.get('step') == 'offer_new_route':
            all_routes = get_all_routes()
            if 1 <= route_num <= len(all_routes):
                selected_route = all_routes[route_num - 1]
                st.session_state.booking_context = {
                    'step': 'traveller_type',
                    'route': selected_route
                }
                return f"🎫 **Great! You selected:**\n**Route {route_num}**: {selected_route[1]} → {selected_route[2]} ({selected_route[5]})\nPrice: ${selected_route[4]:.2f}\n\nPlease choose traveller type:\n- Type '**adult**' for adult ticket\n- Type '**child**' for child ticket (50% discount)"
            else:
                return f"❌ Invalid route number. Please choose between 1 and {len(all_routes)}."
        
        # General route selection from all routes
        routes = get_all_routes()
        if 1 <= route_num <= len(routes):
            selected_route = routes[route_num - 1]
            st.session_state.booking_context = {
                'step': 'traveller_type',
                'route': selected_route
            }
            return f"🎫 Great! You selected:\n**Route {route_num}**: {selected_route[1]} → {selected_route[2]} ({selected_route[5]})\nPrice: ${selected_route[4]:.2f}\n\nPlease choose traveller type:\n- Type '**adult**' for adult ticket\n- Type '**child**' for child ticket (50% discount)"
        else:
            return f"❌ Invalid route number. We have {len(routes)} routes available. Please choose between 1 and {len(routes)}.\n\n💡 Type '**show routes**' to see all available routes again."
    # PRIORITY 4: Handle booking queries (show bookings) - MUST be before other logic
    if any(word in message for word in ["show bookings", "my bookings", "booking history", "bookings for", "all bookings", "bookings under", "bookings of", "booking queries", "show all booking", "all booking", "provide all my bookings", "all my bookings", "provide all"]):
        
        # Check if this is a request for ALL system bookings (no specific user)
        if any(phrase in message for phrase in ["provide all", "provide all my bookings", "all my bookings"]) and "for" not in message and "under" not in message and "of" not in message:
            # This is a request for ALL system bookings with calculations
            try:
                # Import the agent if not already available
                if 'agent' not in st.session_state or st.session_state.agent is None:
                    from agent_repl import TravelBookingAgent
                    st.session_state.agent = TravelBookingAgent()
                
                # Use the new provide_all_bookings intent directly
                with capture_stdout() as captured:
                    result = st.session_state.agent.process_command('provide all bookings', 'local')
                    agent_output = captured.getvalue()
                
                if agent_output.strip():
                    # Format the output nicely for Streamlit
                    response = "� **ALL BOOKINGS IN SYSTEM - Complete Analysis:**\n\n"
                    response += "```\n"
                    response += agent_output.strip()
                    response += "\n```\n\n"
                    response += "� **Want specific user data?** Try:\n"
                    response += "• 'show bookings for [username]' - Individual user analysis\n"
                    response += "• 'total price for [username]' - Quick spending summary"
                    return response
                else:
                    return "📋 **No bookings found in the system.**\n\nThe system is ready for new bookings! Users can log in and start booking trips."
                
            except Exception as e:
                return f"❌ Error retrieving all system bookings: {str(e)}\n\nPlease try again or contact support."
        
        # Handle user-specific booking queries
        # Enhanced username extraction to catch any username pattern
        import re
        # More flexible regex patterns to catch variations like "booking queries under nikitha"
        username_match = re.search(r'(?:for|of|under|show bookings? (?:queries? )?of|bookings? for|bookings? of|bookings? under|all bookings? under|show all bookings? under|booking queries? under|all booking queries? under)\s+([a-zA-Z0-9_]+)', message)
        if username_match:
            requested_user = username_match.group(1)
        else:
            # Check for "my bookings" when user is logged in
            if any(phrase in message for phrase in ["my bookings", "show my bookings"]) and "provide all" not in message:
                if not st.session_state.chat_user_authenticated:
                    return "🔐 Please log in first to view your bookings.\n\nType 'login' to get started!"
                requested_user = st.session_state.chat_current_user
            else:
                # Also check for pattern like "nikitha bookings" or "john bookings"  
                username_match = re.search(r'([a-zA-Z0-9_]+)\s+(?:bookings?|booking queries?)', message)
                if username_match:
                    requested_user = username_match.group(1)
                else:
                    # If no specific username is mentioned and user is not logged in, ask for username
                    if not st.session_state.chat_user_authenticated:
                        return "🔐 Please specify a username or log in first to view bookings.\n\n💡 **Examples:**\n• 'show bookings for nikitha'\n• 'all bookings under john'\n• 'show all booking queries under nikitha'\n• Or type 'login' to access your bookings"
                    requested_user = st.session_state.chat_current_user
        
        # Execute REPL command to get detailed booking information
        try:
            # Import the agent if not already available
            if 'agent' not in st.session_state or st.session_state.agent is None:
                from agent_repl import TravelBookingAgent
                st.session_state.agent = TravelBookingAgent()
            
            # Capture REPL output
            with capture_stdout() as captured:
                result = st.session_state.agent.process_command(f'show me all bookings under {requested_user}', 'local')
                agent_output = captured.getvalue()
            
            if agent_output.strip():
                # Format the output for better readability
                formatted_output = agent_output.strip()
                
                # DEBUG: Let's see what we're getting
                print(f"DEBUG: Agent output contains 'Booking ID:': {'Booking ID:' in formatted_output}")
                print(f"DEBUG: Agent output first 200 chars: {formatted_output[:200]}")
                print(f"DEBUG: Full output length: {len(formatted_output)}")
                
                # ROBUST detection: Only return "no bookings" if we explicitly see the no bookings message AND no booking IDs
                has_booking_ids = "Booking ID:" in formatted_output
                has_no_bookings_msg = "No bookings found" in formatted_output
                
                print(f"DEBUG: has_booking_ids = {has_booking_ids}, has_no_bookings_msg = {has_no_bookings_msg}")
                
                # If we have booking IDs, proceed with parsing regardless of any other messages
                if not has_booking_ids and has_no_bookings_msg:
                    return f"📋 **No bookings found for {requested_user}**\n\nLooks like {requested_user} hasn't made any bookings yet. Ready to book your first trip? Just say 'book ticket' to get started!"
                
                # If we have booking IDs, parse and display them
                if has_booking_ids:
                    print(f"DEBUG: Entering booking parsing logic with {len(formatted_output)} chars")
                    
                    # First, separate the summary section from the booking data
                    summary_section = ""
                    booking_data = formatted_output
                    
                    # Look for the summary section and extract it
                    if "ROUTE-WISE SUMMARY" in formatted_output:
                        # Find the last occurrence of the separator
                        separator = "=================================================="
                        last_separator_index = formatted_output.rfind(separator)
                        
                        if last_separator_index != -1:
                            # Everything before the last separator is booking data
                            booking_data = formatted_output[:last_separator_index].strip()
                            # Everything after the last separator is summary
                            summary_section = formatted_output[last_separator_index + len(separator):].strip()
                        
                        print(f"DEBUG: After improved split - booking_data length: {len(booking_data)}, summary_section length: {len(summary_section)}")
                    else:
                        # No summary section, use all data as booking data
                        booking_data = formatted_output
                        print(f"DEBUG: No summary section found, using full data length: {len(booking_data)}")
                    
                    print(f"DEBUG: booking_data length: {len(booking_data)}, summary_section length: {len(summary_section)}")
                    
                    # Now split the booking data by "Booking ID:" to get individual bookings
                    booking_parts = booking_data.split("Booking ID:")
                    print(f"DEBUG: Found {len(booking_parts)} booking parts after split")
                    
                    response = f"📋 **REPL Booking Analysis for {requested_user.title()}:**\n\n"
                    
                    booking_count = 0
                    
                    for i, part in enumerate(booking_parts):
                        part = part.strip()
                        print(f"DEBUG: Processing part {i}: length {len(part)}, first 50 chars: {part[:50] if part else 'EMPTY'}")
                        
                        if not part:
                            continue
                        
                        # Skip non-booking parts (like headers and user info)
                        if ("Found EXACT user:" in part or 
                            "SHOWING ALL BOOKINGS:" in part or 
                            len(part.split('\n')) < 3):  # Too short to be a real booking
                            print(f"DEBUG: Skipping part {i} - header or too short")
                            continue
                        
                        # This is a booking - extract the ID and create separate section
                        lines = part.split('\n')
                        if lines and lines[0].strip():
                            # Try to extract booking ID number
                            first_line = lines[0].strip()
                            booking_id_parts = first_line.split()
                            print(f"DEBUG: First line: '{first_line}', parts: {booking_id_parts}")
                            
                            if booking_id_parts and booking_id_parts[0].isdigit():
                                booking_id = booking_id_parts[0]
                                booking_count += 1
                                
                                print(f"DEBUG: Found valid booking ID: {booking_id} (count: {booking_count})")
                                
                                # MAXIMUM separation between each booking
                                if booking_count > 1:
                                    response += "\n\n" + "="*50 + "\n\n"
                                
                                response += f"## 🎫 **BOOKING ID: {booking_id}**\n\n"
                                response += "```\n"
                                # Reconstruct the complete booking info for this ID only
                                response += f"Booking ID: {booking_id}\n"
                                response += part
                                response += "\n```\n\n"
                            else:
                                print(f"DEBUG: First part not a digit: {booking_id_parts}")
                    
                    print(f"DEBUG: Final booking_count: {booking_count}")
                    
                    # If no bookings were actually found during parsing
                    if booking_count == 0:
                        print("DEBUG: No bookings found during parsing, returning no bookings message")
                        return f"📋 **No bookings found for {requested_user}**\n\nLooks like {requested_user} hasn't made any bookings yet. Ready to book your first trip? Just say 'book ticket' to get started!"
                    
                    # Add summary section if it exists
                    if summary_section:
                        response += "\n\n" + "="*50 + "\n\n"
                        response += "## 💰 **SUMMARY ANALYSIS**\n\n"
                        response += "```\n"
                        response += summary_section
                        response += "\n```\n\n"
                    
                    # Add interactive suggestions
                    response += f"💡 **Need more analysis?** Try:\n"
                    response += f"• 'total price for {requested_user}' - See spending summary\n"
                    response += f"• 'explain booking [ID]' - Get detailed breakdown for specific booking\n"
                    response += f"• 'book ticket' - Make a new booking"
                    
                    print(f"DEBUG: Returning response with length: {len(response)}")
                    return response
                
                # Fallback if no booking IDs found
                return f"📋 **No bookings found for {requested_user}**\n\nLooks like {requested_user} hasn't made any bookings yet. Ready to book your first trip? Just say 'book ticket' to get started!"
            else:
                return f"❌ No booking information found for {requested_user}."
                
        except Exception as e:
            return f"❌ Error retrieving bookings: {str(e)}\n\nPlease try again or contact support."
    
    # Handle requests for ALL bookings in the system (admin view)
    if any(phrase in message for phrase in ["all bookings", "show all bookings", "system bookings", "every booking"]):
        if "for" not in message and "under" not in message and "of" not in message:
            # This is a request for ALL system bookings, not user-specific
            try:
                # Import the agent if not already available
                if 'agent' not in st.session_state or st.session_state.agent is None:
                    from agent_repl import TravelBookingAgent
                    st.session_state.agent = TravelBookingAgent()
                
                # Use the new provide_all_bookings intent for detailed analysis
                with capture_stdout() as captured:
                    result = st.session_state.agent.process_command('provide all bookings', 'local')
                    agent_output = captured.getvalue()
                
                if agent_output.strip():
                    return f"📋 **All Bookings in System - Complete Analysis:**\n\n```\n{agent_output.strip()}\n```\n\n💡 **Want user-specific bookings?** Try:\n• 'show bookings for [username]' - See specific user's bookings\n• 'total price for [username]' - See spending summary"
                else:
                    return "📋 No bookings found in the system."
                    
            except Exception as e:
                return f"❌ Error retrieving all system bookings: {str(e)}\n\nPlease try again or contact support."
    
    
    # Handle login requests (more conversational and guided)
    if any(word in message for word in ["login", "log in", "sign in", "signin"]):
        if message.startswith("login "):
            # Direct login format
            parts = message.split(" ", 2)
            if len(parts) >= 3:
                username = parts[1]
                password = parts[2]
                user_id = authenticate_user(username, password)
                if user_id:
                    st.session_state.chat_user_authenticated = True
                    st.session_state.chat_current_user = username
                    st.session_state.chat_current_user_id = user_id
                    return f"🎉 Welcome back, {username}! You're now logged in and ready to book tickets.\n\n🌍 **What would you like to do today?**\n\n**Choose an option:**\n1️⃣ **Book from existing routes** - See available flights and book\n2️⃣ **Add new route** - Request a new route to be added\n\nJust type **'1'** or **'2'** or say **'existing routes'** or **'new route'**"
                else:
                    return "❌ Hmm, those credentials don't seem right. Please check your username and password and try again.\n\n💡 Format: login username password"
            else:
                return "Please provide both username and password.\n\n💡 Format: login username password\n\nFor example: login john mypassword123"
        else:
            # Interactive login request - ask for username first
            st.session_state.booking_context = {'step': 'asking_username'}
            return "👋 Great! I'll help you log in step by step.\n\n🔐 **What's your username?**\n\nJust type your username and I'll ask for your password next."
    
    # Handle travel planning requests (natural conversation)
    if any(word in message for word in ["want to go", "travel to", "go to", "trip to", "visit"]):
        if not st.session_state.chat_user_authenticated:
            # Set login context AND save travel intent
            st.session_state.booking_context = {
                'step': 'asking_username',
                'travel_intent': message  # Save what they wanted to do
            }
            return "🔐 I'd love to help you plan your trip! But first, let me get you logged in.\n\n👋 **What's your username?**\n\nOnce you're logged in, I'll help you find the perfect route!"
        
        # User wants to travel - ask what they want to do
        st.session_state.booking_context = {'step': 'choose_action'}
        return "🌍 **Great! What would you like to do?**\n\n**Choose an option:**\n1️⃣ **Book from existing routes** - See available flights and book\n2️⃣ **Add new route** - Request a new route to be added\n\nJust type **'1'** or **'2'** or say **'existing routes'** or **'new route'**"
    
    
    # Handle action choice (existing routes vs new route)
    if st.session_state.booking_context.get('step') == 'choose_action':
        if any(word in message for word in ["1", "existing", "book existing", "existing routes"]):
            # User wants to book existing routes
            st.session_state.booking_context = {'step': 'asking_destination'}
            return "🎯 **Great! Let's book from existing routes!**\n\n✈️ **Where would you like to go?**\nJust tell me your destination city, for example:\n• 'Paris'\n• 'Mumbai'\n• 'Tokyo'\n\nWhat's your dream destination?"
        elif any(word in message for word in ["2", "new", "add", "new route"]):
            # User wants to add new route
            st.session_state.booking_context = {'step': 'new_route_origin'}
            return "🆕 **Perfect! Let's add a new route!**\n\n🏠 **Where should this new route start from?**\nPlease tell me the origin city:\n\nFor example: 'Mumbai', 'Delhi', 'Chennai'"
        else:
            return "Please choose an option:\n\n1️⃣ Type **'1'** or **'existing routes'** to book from existing routes\n2️⃣ Type **'2'** or **'new route'** to add a new route\n\nWhat would you like to do?"
    
    # Handle new route creation - asking for origin
    if st.session_state.booking_context.get('step') == 'new_route_origin':
        origin = message.strip().title()
        st.session_state.booking_context = {
            'step': 'new_route_destination',
            'new_route_origin': origin
        }
        return f"✅ **Origin: {origin}**\n\n🎯 **Where should this route go to?**\nPlease tell me the destination city:\n\nFor example: 'Dubai', 'Singapore', 'London'"
    
    # Handle new route creation - asking for destination
    if st.session_state.booking_context.get('step') == 'new_route_destination':
        destination = message.strip().title()
        origin = st.session_state.booking_context.get('new_route_origin')
        st.session_state.booking_context = {
            'step': 'new_route_transport',
            'new_route_origin': origin,
            'new_route_destination': destination
        }
        return f"✅ **Route: {origin} → {destination}**\n\n🚊 **What type of transport?**\nChoose from:\n• **'flight'** - Air travel\n• **'bus'** - Road travel\n• **'train'** - Rail travel\n\nWhat type would you prefer?"
    
    # Handle new route creation - asking for transport type
    if st.session_state.booking_context.get('step') == 'new_route_transport':
        if message.lower() in ['flight', 'bus', 'train']:
            transport = message.lower()
            origin = st.session_state.booking_context.get('new_route_origin')
            destination = st.session_state.booking_context.get('new_route_destination')
            st.session_state.booking_context = {
                'step': 'new_route_price',
                'new_route_origin': origin,
                'new_route_destination': destination,
                'new_route_transport': transport
            }
            return f"✅ **Transport: {transport.title()}**\n\n💰 **What should be the base price?**\nEnter the price in dollars (just the number):\n\nFor example: 450, 750, 1200"
        else:
            return "Please choose a valid transport type:\n• **'flight'**\n• **'bus'**\n• **'train'**"
    
    # Handle new route creation - asking for price
    if st.session_state.booking_context.get('step') == 'new_route_price':
        try:
            price = float(message.strip())
            origin = st.session_state.booking_context.get('new_route_origin')
            destination = st.session_state.booking_context.get('new_route_destination')
            transport = st.session_state.booking_context.get('new_route_transport')
            st.session_state.booking_context = {
                'step': 'new_route_seats',
                'new_route_origin': origin,
                'new_route_destination': destination,
                'new_route_transport': transport,
                'new_route_price': price
            }
            return f"✅ **Price: ${price}**\n\n🪑 **How many total seats?**\nEnter the number of seats available:\n\nFor example: 100, 150, 200"
        except ValueError:
            return "Please enter a valid price (just numbers):\nFor example: 450, 750, 1200"
    
    # Handle new route creation - asking for seats
    if st.session_state.booking_context.get('step') == 'new_route_seats':
        try:
            seats = int(message.strip())
            origin = st.session_state.booking_context.get('new_route_origin')
            destination = st.session_state.booking_context.get('new_route_destination')
            transport = st.session_state.booking_context.get('new_route_transport')
            price = st.session_state.booking_context.get('new_route_price')
            
            # Add route to database
            conn = sqlite3.connect('travel.db')
            c = conn.cursor()
            c.execute('''INSERT INTO routes 
                         (origin, destination, departure_time, base_price, transport_type, seats_available, seats_total) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                      (origin, destination, '2025-01-15 10:00:00', price, transport, seats, seats))
            conn.commit()
            route_id = c.lastrowid
            conn.close()
            
            # Clear context and offer immediate booking of the new route
            st.session_state.booking_context = {
                'step': 'offer_immediate_booking',
                'new_route_id': route_id,
                'new_route_info': (route_id, origin, destination, '2025-01-15 10:00:00', price, transport, seats)
            }
            
            return f"🎉 **NEW ROUTE ADDED SUCCESSFULLY!**\n\n📋 **Route Details:**\n• **Route ID:** {route_id}\n• **Route:** {origin} → {destination}\n• **Transport:** {transport.title()}\n• **Price:** ${price}\n• **Seats:** {seats}\n\n✈️ **Would you like to book this route right now?**\n\n**Options:**\n• Type '**yes**' or '**book**' to book this route immediately\n• Type '**show routes**' to see all routes\n• Type '**add another**' to add more routes"
        except ValueError:
            return "Please enter a valid number of seats:\nFor example: 100, 150, 200"

    # Handle immediate booking after adding new route
    if st.session_state.booking_context.get('step') == 'offer_immediate_booking':
        if any(word in message for word in ["yes", "book", "book this", "book it"]):
            # User wants to book the newly added route immediately
            new_route_info = st.session_state.booking_context.get('new_route_info')
            st.session_state.booking_context = {
                'step': 'traveller_type',
                'route': new_route_info
            }
            route_id, origin, destination, departure, price, transport, seats = new_route_info
            return f"🎫 **Great! You selected the new route:**\n{origin} → {destination} ({transport})\nPrice: ${price:.2f}\n\nPlease choose traveller type:\n- Type '**adult**' for adult ticket\n- Type '**child**' for child ticket (50% discount)"
        elif any(word in message for word in ["show routes", "show all", "all routes"]):
            # Show all routes including the new one
            routes = get_all_routes()
            st.session_state.booking_context = {}
            response = "📋 **All Available Routes (including your new route):**\n\n"
            for i, route in enumerate(routes, 1):
                response += f"**{i}.** {route[1]} → {route[2]} ({route[5]}) - ${route[4]:.2f}\n"
            response += f"\n💡 Type a route number (1-{len(routes)}) to book!"
            return response
        elif any(word in message for word in ["add another", "add more"]):
            # Start adding another route
            st.session_state.booking_context = {'step': 'new_route_origin'}
            return "🆕 **Perfect! Let's add another route!**\n\n🏠 **Where should this new route start from?**\nPlease tell me the origin city:\n\nFor example: 'Mumbai', 'Delhi', 'Chennai'"
        else:
            return "🤔 I didn't understand that. Please choose:\n• Type '**yes**' or '**book**' to book the route you just added\n• Type '**show routes**' to see all available routes\n• Type '**add another**' to add more routes"

    # Handle origin input (NEW - always ask origin first after login)
    if st.session_state.booking_context.get('step') == 'asking_origin':
        origin = message.strip().title()
        st.session_state.booking_context = {
            'step': 'asking_destination',
            'origin': origin
        }
        return f"✅ **Starting from: {origin}**\n\n🎯 **Where would you like to go?**\nPlease tell me your destination city:\n\nFor example:\n• 'Paris'\n• 'Mumbai'\n• 'Dubai'\n• 'Singapore'\n\nWhat's your destination?"
    
    # Handle destination input (UPDATED - now checks for existing routes)
    if st.session_state.booking_context.get('step') == 'asking_destination':
        destination = message.strip().title()
        origin = st.session_state.booking_context.get('origin')
        
        # Search for routes between origin and destination
        matching_routes = search_routes(origin, destination)
        
        if matching_routes:
            # Routes exist - show them for booking
            response = f"🎉 **Perfect! I found {len(matching_routes)} route(s) from {origin} to {destination}:**\n\n"
            for i, route in enumerate(matching_routes, 1):
                response += f"**{i}.** {route[1]} → {route[2]} ({route[5]})\n"
                response += f"   💰 Price: ${route[4]:.2f} | 🪑 Available seats: {route[6]}\n"
                response += f"   ⏰ Departure: {route[3]}\n\n"
            
            # Dynamic message based on number of routes
            if len(matching_routes) == 1:
                response += "**Perfect! This is exactly what you're looking for!**\nJust type **'1'** to book this route!"
            else:
                response += "**Which route looks good to you?**\nJust say the number, like '1' or '2'!"
            
            # Store matching routes for booking
            st.session_state.booking_context = {
                'step': 'route_selection',
                'available_routes': matching_routes,
                'origin': origin,
                'destination': destination
            }
            return response
        else:
            # No routes exist - offer to add new route
            st.session_state.booking_context = {
                'step': 'offer_new_route',
                'origin': origin,
                'destination': destination
            }
            
            # Show what routes ARE available
            all_routes = get_all_routes()
            response = f"😔 **No direct routes found from {origin} to {destination}**\n\n"
            
            if all_routes:
                response += "🗺️ **Here are our current available routes:**\n"
                for i, route in enumerate(all_routes[:5], 1):  # Show first 5 routes
                    response += f"{i}. {route[1]} → {route[2]} ({route[5]}) - ${route[4]:.2f}\n"
                if len(all_routes) > 5:
                    response += f"   ... and {len(all_routes) - 5} more routes\n"
                response += "\n"
            
            response += f"🆕 **Would you like me to help add {origin} → {destination} as a new route?**\n\n"
            response += "**Options:**\n"
            response += "• Type '**yes**' or '**add route**' to create this new route\n"
            response += "• Type '**show all**' to see all available routes\n"
            response += "• Type '**change**' to try different cities\n"
            response += f"• Type a **route number** (1-{len(all_routes) if all_routes else 0}) to book existing route\n\n"
            response += "What would you like to do?"
            return response
    
    # Handle origin input
    if st.session_state.booking_context.get('step') == 'asking_origin':
        origin = message.strip().title()
        destination = st.session_state.booking_context.get('destination')
        
        # Search for routes
        matching_routes = search_routes(origin, destination)
        
        if matching_routes:
            # Routes exist - show available options
            response = f"🎉 **Perfect! I found routes from {origin} to {destination}:**\n\n"
            for i, route in enumerate(matching_routes, 1):
                response += f"**{i}.** {route[1]} → {route[2]} ({route[5]})\n"
                response += f"   💰 Price: ${route[4]:.2f} | 🪑 Available seats: {route[6]}\n"
                response += f"   ⏰ Departure: {route[3]}\n\n"
            
            # Dynamic message based on number of routes
            if len(matching_routes) == 1:
                response += "**Perfect! This is exactly what you're looking for!**\nJust type **'1'** to book this route!"
            else:
                response += "**Which route looks good to you?**\nJust say the number, like '1' or '2'!"
            
            # Store matching routes for booking
            st.session_state.booking_context = {
                'step': 'route_selection',
                'available_routes': matching_routes,
                'origin': origin,
                'destination': destination
            }
            return response
        else:
            # No routes exist - show available alternatives and suggest adding route
            all_routes = get_all_routes()
            st.session_state.booking_context = {}
            
            response = f"😔 **Sorry, I couldn't find any direct routes from {origin} to {destination}.**\n\n"
            
            # Show what routes ARE available
            if all_routes:
                response += "� **Here are our current available routes:**\n"
                for route in all_routes[:8]:  # Show first 8 routes
                    response += f"• {route[1]} → {route[2]} ({route[5]})\n"
                if len(all_routes) > 8:
                    response += f"• ... and {len(all_routes) - 8} more routes\n"
                response += "\n"
            
            response += "🔍 **What you can do:**\n"
            response += f"1. **Book available route**: Choose from routes above by saying 'book [number]'\n"
            response += f"2. **Check nearby cities**: Try '{destination}' from Delhi, Bengaluru, or Chennai\n"
            response += f"3. **Request new route**: I can help you request {origin} to {destination}\n"
            response += f"4. **See all routes**: Say 'show routes' for complete list\n\n"
            response += f"💡 **Good news!** Admin can easily add the {origin} to {destination} route you want!\n"
            response += "**What would you like to do?**"
            return response
    
    # Handle offer new route responses
    if st.session_state.booking_context.get('step') == 'offer_new_route':
        origin = st.session_state.booking_context.get('origin')
        destination = st.session_state.booking_context.get('destination')
        
        if any(word in message for word in ["yes", "add", "create", "new"]):
            # User wants to add new route
            st.session_state.booking_context = {
                'step': 'new_route_transport',
                'new_route_origin': origin,
                'new_route_destination': destination
            }
            return f"🎉 **Great! Let's add the {origin} → {destination} route!**\n\n🚊 **What type of transport?**\nChoose from:\n• **'flight'** - Air travel\n• **'bus'** - Road travel\n• **'train'** - Rail travel\n\nWhat type would you prefer?"
        elif any(word in message for word in ["show all", "all routes", "show routes"]):
            # Show all routes
            routes = get_all_routes()
            st.session_state.booking_context = {}
            if not routes:
                return "📋 No routes available in the system."
            
            response = "📋 **All Available Routes:**\n\n"
            for i, route in enumerate(routes, 1):
                response += f"**{i}.** {route[1]} → {route[2]} ({route[5]}) - ${route[4]:.2f}\n"
            response += f"\n💡 Type a route number (1-{len(routes)}) to book!"
            return response
        elif any(word in message for word in ["change", "different", "try again"]):
            # Start over with new cities
            st.session_state.booking_context = {'step': 'asking_origin'}
            return "🔄 **Let's try different cities!**\n\n🏠 **Where will you be traveling from?**\nPlease tell me your origin city (starting point):"
        else:
            return f"🤔 I didn't understand that. Please choose:\n• Type '**yes**' to add {origin} → {destination} route\n• Type '**show all**' to see available routes\n• Type '**change**' to try different cities\n• Type a **route number** to book existing route"
    
    # Handle route addition requests
    if any(word in message for word in ["add route", "new route", "create route", "route request"]):
        return "🔧 **Route Addition Request**\n\nTo add new routes, an admin needs to:\n\n1. **Access admin panel** (if available)\n2. **Add to database** directly\n3. **Contact system administrator**\n\n💡 **For immediate help:**\n• Tell me which route you need (from where to where)\n• I can provide the exact SQL commands for admin\n• Say 'help admin' for detailed instructions\n\nWhich route would you like to request?"
    
    # Admin help
    if any(word in message for word in ["help admin", "admin help", "admin instructions"]):
        return """🔧 **Admin Route Management Guide**

**To add a new route to the database:**

**Method 1: SQL Command**
```sql
INSERT INTO routes (origin, destination, departure_time, base_price, transport_type, seats_available, seats_total) 
VALUES ('CityA', 'CityB', '2025-01-15 10:00:00', 500.00, 'flight', 100, 100);
```

**Method 2: Python Script**
```python
import sqlite3
conn = sqlite3.connect('travel.db')
c = conn.cursor()
c.execute("INSERT INTO routes (origin, destination, departure_time, base_price, transport_type, seats_available, seats_total) VALUES (?, ?, ?, ?, ?, ?, ?)", 
          ('Origin', 'Destination', '2025-01-15 10:00:00', 500.00, 'flight', 100, 100))
conn.commit()
conn.close()
```

**Fields to specify:**
• origin: Starting city
• destination: End city  
• departure_time: Format 'YYYY-MM-DD HH:MM:SS'
• base_price: Price in dollars
• transport_type: 'flight', 'bus', 'train'
• seats_available: Current available seats
• seats_total: Total seats capacity

Need help with a specific route? Just ask!"""
    
    # Show routes
    if any(word in message for word in ["routes", "flights", "show"]):
        routes = get_all_routes()
        if not routes:
            return "No routes available at the moment."
        
        response = "📋 Available Routes:\n\n"
        for i, route in enumerate(routes, 1):
            response += f"{i}. {route[1]} → {route[2]} ({route[5]})\n"
            response += f"   Price: ${route[4]:.2f} | Available seats: {route[6]}\n"
            response += f"   Departure: {route[3]}\n\n"
        response += "To book a ticket, say: 'book [route number]' or 'book ticket to [destination]'"
        return response
    
    # Help
    if "help" in message:
        help_text = """Here's what I can help you with:

🔐 **Login**: Type 'login username password'
✈️ **View Routes**: Say 'show routes' or 'flights'
🎫 **Book Ticket**: 
   • 'book [route number]' - book specific route
   • 'book from [origin] to [destination]' - smart search
   • 'book ticket from Delhi to Mumbai' - natural language
💰 **Check Prices**: Say 'price' or 'pricing'
❓ **Help**: Say 'help'

**Smart Booking Examples:**
• "I need to book a ticket from Delhi to Mumbai"
• "Book flight from NYC to LA"
• "Book from Hyderabad to Chennai"

**If route doesn't exist:**
• I'll suggest available alternatives
• Admin can add new routes using admin panel
• Contact admin to add your desired route

**Booking Process:**
1. Login with your credentials
2. Specify your origin and destination OR choose from available routes
3. Select traveller type (adult/child)
4. Confirm booking"""
        return help_text
    
    # Booking flow - Enhanced with location intelligence
    if any(word in message for word in ["book", "reserve", "buy", "ticket"]):
        if not st.session_state.chat_user_authenticated:
            return "🔐 Oops! Looks like you need to log in first to book tickets.\n\n👋 No worries - it's super easy!\nJust type: **login username password**\n\nFor example: login john mypassword123\n\n✨ Once you're logged in, I'll help you find and book the perfect ticket!"
        
        # Extract locations from message
        origin, destination = extract_locations_from_message(message)
        
        if origin and destination:
            # User specified both origin and destination
            matching_routes = search_routes(origin, destination)
            
            if matching_routes:
                # Routes exist - show available options
                response = f"✈️ Great! I found routes from {origin.title()} to {destination.title()}:\n\n"
                for i, route in enumerate(matching_routes, 1):
                    response += f"{i}. {route[1]} → {route[2]} ({route[5]})\n"
                    response += f"   Price: ${route[4]:.2f} | Available seats: {route[6]}\n"
                    response += f"   Departure: {route[3]}\n\n"
                response += "Which route would you like to book? Say 'book [number]' to select."
                
                # Store matching routes for booking
                st.session_state.booking_context = {
                    'step': 'route_selection',
                    'available_routes': matching_routes
                }
                return response
            else:
                # No routes exist - suggest admin contact with better alternatives
                all_routes = get_all_routes()
                response = f"🚫 Sorry, I couldn't find any routes from {origin.title()} to {destination.title()}.\n\n"
                
                # Show sample of available routes
                if all_routes:
                    response += "📋 **Current available routes include:**\n"
                    for route in all_routes[:6]:  # Show first 6 routes
                        response += f"• {route[1]} → {route[2]} ({route[5]})\n"
                    if len(all_routes) > 6:
                        response += f"• ... and {len(all_routes) - 6} more\n"
                    response += "\n"
                
                response += "💡 **Options for you:**\n"
                response += f"1. **Book existing route**: Say 'show routes' to see all options\n"
                response += f"2. **Try nearby cities**: Maybe from Delhi or Bengaluru to {destination.title()}?\n"
                response += f"3. **New route request**: Admin can add {origin.title()} to {destination.title()}\n\n"
                response += f"🎯 **The {origin.title()} to {destination.title()} route can be added easily!**\n"
                response += "Would you like to see available routes instead? Say 'show routes'."
                return response
        
        # Extract route number if specified (improved detection)
        route_num = None
        if message.isdigit():
            # If the entire message is just a number, treat it as route selection
            route_num = int(message)
        elif "book " in message:
            parts = message.split()
            for part in parts:
                if part.isdigit():
                    route_num = int(part)
                    break
        
        # Handle route number selection
        if route_num:
            # Check if we're in route selection mode
            if st.session_state.booking_context.get('step') == 'route_selection':
                available_routes = st.session_state.booking_context.get('available_routes', [])
                if 1 <= route_num <= len(available_routes):
                    selected_route = available_routes[route_num - 1]
                    st.session_state.booking_context = {
                        'step': 'traveller_type',
                        'route': selected_route
                    }
                    return f"🎫 Great! You selected:\n{selected_route[1]} → {selected_route[2]} ({selected_route[5]})\nPrice: ${selected_route[4]:.2f}\n\nPlease choose traveller type:\n- Type 'adult' for adult ticket\n- Type 'child' for child ticket (50% discount)"
                else:
                    return f"❌ Invalid route number. Please choose between 1 and {len(available_routes)}."
            else:
                # General route selection from all routes
                routes = get_all_routes()
                if 1 <= route_num <= len(routes):
                    selected_route = routes[route_num - 1]
                    st.session_state.booking_context = {
                        'step': 'traveller_type',
                        'route': selected_route
                    }
                    return f"🎫 Great! You selected:\n{selected_route[1]} → {selected_route[2]} ({selected_route[5]})\nPrice: ${selected_route[4]:.2f}\n\nPlease choose traveller type:\n- Type 'adult' for adult ticket\n- Type 'child' for child ticket (50% discount)"
                else:
                    return f"❌ Invalid route number. Please choose between 1 and {len(routes)}."
        else:
            # Show all available routes for booking
            routes = get_all_routes()
            if not routes:
                return "🚫 No routes available at the moment. Please contact admin to add routes."
            
            response = "🎫 **Which route would you like to book?**\n\n"
            for i, route in enumerate(routes, 1):
                response += f"**{i}.** {route[1]} → {route[2]} ({route[5]}) - ${route[4]:.2f}\n"
            response += "\n💡 **Tips:**\n"
            response += "• Type the **route number** (like '11' for Hyd → Bengaluru)\n"
            response += "• Say 'book from [origin] to [destination]' to search specific routes\n"
            response += "• If your desired route doesn't exist, contact admin to add it"
            return response
    
    # Handle traveller type selection
    if st.session_state.booking_context.get('step') == 'traveller_type':
        if message in ['adult', 'child']:
            route = st.session_state.booking_context['route']
            traveller_type = message
            
            # Get available discounts for this user
            conn = sqlite3.connect('travel.db')
            c = conn.cursor()
            
            # Get user loyalty points
            c.execute('SELECT loyalty_points FROM users WHERE id=?', (st.session_state.chat_current_user_id,))
            user_row = c.fetchone()
            loyalty_points = user_row[0] if user_row else 0
            
            # Get available discounts
            c.execute('''SELECT id, name, percentage, user_type, min_points 
                         FROM discounts 
                         WHERE (user_type=? OR user_type IS NULL OR user_type='') 
                         AND min_points<=? 
                         ORDER BY percentage DESC''', 
                      (traveller_type, loyalty_points))
            available_discounts = c.fetchall()
            conn.close()
            
            if available_discounts:
                # Show discount options
                st.session_state.booking_context.update({
                    'step': 'discount_selection',
                    'traveller_type': traveller_type,
                    'available_discounts': available_discounts
                })
                
                response = f"🎉 **Great! You qualify for discounts!**\n\n"
                response += f"✅ Traveller type: **{traveller_type.title()}**\n"
                if traveller_type == 'child':
                    response += f"🎈 **Child discount: 50% off** (automatically applied)\n\n"
                
                response += f"🎟️ **Choose your preferred discount:**\n\n"
                for i, discount in enumerate(available_discounts, 1):
                    discount_id, name, percentage, user_type, min_points = discount
                    response += f"**{i}.** Apply `{name}` code - **Save {percentage}%!**"
                    if user_type:
                        response += f" (for {user_type})"
                    if min_points > 0:
                        response += f" (requires {min_points}+ points)"
                    response += f"\n"
                
                response += f"\n**0.** Skip discounts - Use standard pricing\n\n"
                response += f"� **Your loyalty points:** {loyalty_points}\n\n"
                response += f"🎯 **Pick your choice:** Type any number from **0** to **{len(available_discounts)}**\n"
                response += f"• **0** = No extra discount (pay standard price)\n"
                response += f"• **1-{len(available_discounts)}** = Apply that specific discount code for maximum savings!"
                
                return response
            else:
                # No additional discounts available, proceed to pricing
                route_id = route[0]
                base_price = route[4]
                final_price = calculate_final_price(base_price, traveller_type, st.session_state.chat_current_user_id)
                
                st.session_state.booking_context.update({
                    'step': 'confirm',
                    'traveller_type': traveller_type,
                    'final_price': final_price,
                    'selected_discount': None
                })
                
                response = f"💰 **Price Calculation:**\n• Base price: ${base_price:.2f}\n• Traveller type: {traveller_type.title()}\n"
                if traveller_type == 'child':
                    response += f"• Child discount: 50% OFF\n"
                response += f"• **Final price: ${final_price:.2f}**\n\n"
                response += f"💡 No additional discounts available for your profile.\n\n"
                response += f"✅ Type **'confirm'** to complete booking or **'cancel'** to abort."
                
                return response
        else:
            return "Please type **'adult'** or **'child'** to select traveller type.\n\n💡 **Reminder:**\n• Adult: Full price\n• Child: 50% discount\n• Additional discounts may be available based on your profile!"
    
    # Handle discount selection
    if st.session_state.booking_context.get('step') == 'discount_selection':
        if message.isdigit():
            choice = int(message)
            available_discounts = st.session_state.booking_context.get('available_discounts', [])
            traveller_type = st.session_state.booking_context.get('traveller_type')
            route = st.session_state.booking_context['route']
            base_price = route[4]
            
            selected_discount = None
            discount_info = "Standard pricing (no discount codes applied)"
            
            if choice == 0:
                # No additional discount
                selected_discount = None
                discount_info = "Standard pricing (no discount codes applied)"
            elif 1 <= choice <= len(available_discounts):
                # Selected a discount
                selected_discount = available_discounts[choice - 1]
                discount_id, name, percentage, user_type, min_points = selected_discount
                discount_info = f"You chose: {name} discount code ({percentage}% savings!)"
            else:
                return f"❌ Invalid choice. Please choose between 0 and {len(available_discounts)}."
            
            # Calculate final price with selected discount
            if selected_discount:
                # Apply the selected discount manually
                price = base_price
                # Apply demand factor first
                conn = sqlite3.connect('travel.db')
                c = conn.cursor()
                c.execute('SELECT seats_available, seats_total FROM routes WHERE id=?', (route[0],))
                route_info = c.fetchone()
                conn.close()
                
                if route_info:
                    seats_left, seats_total = route_info
                    demand_factor = 1 + (1 - seats_left / seats_total) * 0.5
                    price = base_price * demand_factor
                
                # Apply child discount
                if traveller_type == 'child':
                    price *= 0.5
                
                # Apply selected discount
                _, name, percentage, user_type, min_points = selected_discount
                price *= (1 - percentage / 100)
                final_price = round(price, 2)
            else:
                # Use standard calculation (without additional discount codes)
                final_price = calculate_final_price(base_price, traveller_type, st.session_state.chat_current_user_id)
            
            st.session_state.booking_context.update({
                'step': 'confirm',
                'traveller_type': traveller_type,
                'final_price': final_price,
                'selected_discount': selected_discount,
                'discount_info': discount_info
            })
            
            response = f"💰 **Final Price Calculation:**\n"
            response += f"• Base price: ${base_price:.2f}\n"
            response += f"• Traveller type: {traveller_type.title()}\n"
            if traveller_type == 'child':
                response += f"• Child discount: 50% OFF\n"
            if selected_discount:
                _, name, percentage, user_type, min_points = selected_discount
                response += f"• Discount code: {name} ({percentage}% OFF)\n"
            response += f"• **Final price: ${final_price:.2f}**\n\n"
            response += f"🎟️ {discount_info}\n\n"
            response += f"✅ Type **'confirm'** to complete booking or **'cancel'** to abort."
            
            return response
        else:
            available_discounts = st.session_state.booking_context.get('available_discounts', [])
            return f"🤔 Please choose a valid option!\n\n**Your choices:**\n• Type **'0'** = Skip all discounts (standard price)\n• Type **'1' to '{len(available_discounts)}'** = Apply that specific discount code\n\n💡 **Example:** Type '1' to apply the first discount, '2' for the second, etc.\nOr type '0' if you prefer standard pricing without any discount codes."
    
    # Handle booking confirmation
    if st.session_state.booking_context.get('step') == 'confirm':
        if message == 'confirm':
            route = st.session_state.booking_context['route']
            traveller_type = st.session_state.booking_context['traveller_type']
            selected_discount = st.session_state.booking_context.get('selected_discount')
            
            # Book the ticket
            result = book_ticket(
                st.session_state.chat_current_user_id,
                route[0],
                None,
                traveller_type
            )
            
            # Clear booking context and mark as completed
            st.session_state.booking_context = {'step': 'booking_completed'}
            
            if 'error' in result:
                return f"❌ Booking failed: {result['error']}"
            else:
                response = f"🎉 **Booking successful!**\n\n"
                response += f"📋 **Booking Details:**\n"
                response += f"• **Booking ID:** {result['booking_id']}\n"
                response += f"• **Route:** {route[1]} → {route[2]}\n"
                response += f"• **Transport:** {route[5]}\n"
                response += f"• **Traveller type:** {traveller_type.title()}\n"
                if selected_discount:
                    _, name, percentage, user_type, min_points = selected_discount
                    response += f"• **Discount applied:** {name} ({percentage}% OFF)\n"
                response += f"• **Price paid:** ${result['price_paid']:.2f}\n"
                response += f"• **Status:** {result['status']}\n\n"
                response += f"🎫 **Thank you for your booking!**\n\n"
                response += f"✅ **Your booking is complete!** You can now:\n"
                response += f"• Type '**show my bookings**' to see all your trips\n"
                response += f"• Type '**book ticket**' to book another trip\n"
                response += f"• Type '**help**' for more options\n"
                response += f"• Or simply continue chatting for assistance!\n\n"
                response += f"🌟 **Enjoy your journey!**"
                
                return response
        
        elif message == 'cancel':
            st.session_state.booking_context = {}
            return "❌ Booking cancelled. How else can I help you?"
        else:
            return "Please type 'confirm' to complete booking or 'cancel' to abort."
    
    # Handle post-booking completion actions
    if st.session_state.booking_context.get('step') == 'booking_completed':
        # Clear the completion flag after first interaction
        st.session_state.booking_context = {}
        
        # Handle the first post-booking action gracefully
        if any(word in message for word in ["show my bookings", "my bookings", "booking history"]):
            # Process the booking request normally - the existing logic will handle it
            pass  # Fall through to booking queries handler
        elif any(word in message for word in ["book ticket", "book", "new booking"]):
            # Start new booking flow
            st.session_state.booking_context = {'step': 'asking_origin'}
            return "🌍 **Great! Let's book another trip!**\n\n🏠 **Where will you be traveling from?**\nPlease tell me your origin city (starting point):\n\nFor example:\n• 'Delhi'\n• 'Mumbai' \n• 'Vijayawada'\n• 'Chennai'\n\nWhat's your starting city?"
        elif any(word in message for word in ["help"]):
            # Fall through to help handler
            pass
        elif any(word in message for word in ["hello", "hi", "thank you", "thanks"]):
            return f"😊 **You're very welcome, {st.session_state.chat_current_user}!**\n\nI'm glad I could help you complete your booking. Feel free to ask if you need anything else - I'm always here to assist with your travel needs!\n\n✈️ **Safe travels!**"
        else:
            # For any other message, provide helpful guidance
            return f"👋 **Thanks for using our booking system, {st.session_state.chat_current_user}!**\n\nYour booking was successful. If you need anything else:\n\n• Type '**show my bookings**' to see all your trips\n• Type '**book ticket**' to book another trip\n• Type '**help**' for more options\n\nWhat would you like to do next?"
    
    # Price inquiry
    if any(word in message for word in ["price", "cost", "how much"]):
        return "💰 Ticket prices depend on:\n- Route and destination\n- Traveller type (child = 50% discount)\n- Seat availability (dynamic pricing)\n- Your loyalty points\n\nTo see exact prices, use 'show routes' or start booking with 'book ticket'."
    
    # Handle total price queries
    if any(word in message for word in ["total price", "total cost", "total spending", "how much spent"]):
        if not st.session_state.chat_user_authenticated:
            return "🔐 Please log in first to view spending information.\n\nType 'login' to get started!"
        
        # Extract username if specified, otherwise use current user
        import re
        username_match = re.search(r'(?:for|of|user)\s+(\w+)', message)
        if username_match:
            requested_user = username_match.group(1)
        else:
            requested_user = st.session_state.chat_current_user
        
        try:
            # Import the agent if not already available
            if 'agent' not in st.session_state or st.session_state.agent is None:
                from agent_repl import TravelBookingAgent
                st.session_state.agent = TravelBookingAgent()
            
            # Capture REPL output
            with capture_stdout() as captured:
                result = st.session_state.agent.process_command(f'total price for user {requested_user}', 'local')
                agent_output = captured.getvalue()
            
            if agent_output.strip():
                return f"💰 **Total Spending Analysis for {requested_user.title()}:**\n\n```\n{agent_output.strip()}\n```\n\n💡 Want to see individual bookings? Ask 'show bookings for {requested_user}'"
            else:
                return f"❌ No spending information found for {requested_user}."
                
        except Exception as e:
            return f"❌ Error calculating total spending: {str(e)}\n\nPlease try again or contact support."
    
    # Greeting (enhanced and more welcoming)
    if any(word in message for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        if st.session_state.chat_user_authenticated:
            return f"Hello again, {st.session_state.chat_current_user}! 😊\n\n🌍 **What would you like to do today?**\n\n**Choose an option:**\n1️⃣ **Book from existing routes** - See available flights and book\n2️⃣ **Add new route** - Request a new route to be added\n3️⃣ **Check my bookings** - View your booking history\n\nJust type **'1'**, **'2'**, **'3'** or describe what you need!"
        else:
            return "👋 **Hello! Welcome to the Travel Booking System!** ✈️\n\nI'm your friendly travel assistant and I'm here to help you:\n• 🎫 **Book tickets** to amazing destinations\n• � **Add new routes** based on your needs\n• 💰 **Get best prices** with automatic discounts\n• 📋 **Manage bookings** easily\n\n🔐 **Ready to start? Please log in first:**\n\nJust say **'login'** and I'll guide you step by step!"
    
    # Default response (more helpful and friendly)
    return "🤔 I'm not quite sure what you're looking for, but I'm here to help!\n\n✨ **Here are some things you can try:**\n• Say '**hello**' for a warm welcome\n• Type '**login username password**' to sign in\n• Say '**show routes**' to see available flights\n• Ask '**help**' for detailed options\n• Try '**book from [city] to [city]**' to find tickets\n\n💬 Feel free to ask me anything about travel booking - I'm here to make your journey smooth!"


# REPL Interface (like agent_repl.py)
def repl_interface():
    """REPL calculation interface"""
    st.markdown('<div class="menu-header">🧮 REPL Calculator</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("← Back to Main Menu"):
            st.session_state.app_mode = "main_menu"
            st.rerun()
    
    st.markdown("### Travel Booking REPL")
    st.markdown('<div class="info-box">Enter commands to calculate prices, check bookings, etc.</div>', unsafe_allow_html=True)
    
    # Display previous REPL output
    if st.session_state.repl_output:
        st.markdown("### 📜 Previous Output:")
        for i, output in enumerate(st.session_state.repl_output[-5:]):  # Show last 5 outputs
            if output.startswith("Command:"):
                st.markdown(f'<div class="command-input">🔸 {output}</div>', unsafe_allow_html=True)
            elif output.startswith("Output:"):
                # Format the output content
                formatted_output = output.replace("Output:\n", "").strip()
                st.markdown(f'<div class="repl-output">📊 REPL Result:\n\n{formatted_output}</div>', unsafe_allow_html=True)
            elif output.startswith("Error:"):
                st.markdown(f'<div class="command-output" style="background: linear-gradient(135deg, #ffebee, #ffcdd2); color: #c62828; border-color: #f44336;">❌ {output}</div>', unsafe_allow_html=True)
    
    # Command input
    command = st.text_input("💻 Enter command:", placeholder="e.g., 'show bookings of nikitha' or 'total price for user nikitha'")
    
    if st.button("🚀 Execute", type="primary") or command:
        if command:
            with st.spinner("🔄 Processing command..."):
                try:
                    # Capture the agent's output
                    with capture_stdout() as captured:
                        result = st.session_state.agent.process_command(command, 'local')
                        agent_output = captured.getvalue()
                    
                    if agent_output.strip():
                        # Store output in session state
                        st.session_state.repl_output.append(f"Command: {command}")
                        st.session_state.repl_output.append(f"Output:\n{agent_output}")
                        
                        # Display output with enhanced formatting
                        st.markdown(f'<div class="command-input">🔸 Command: {command}</div>', unsafe_allow_html=True)
                        
                        # Format the agent output for better readability with booking separation
                        formatted_output = agent_output.strip()
                        
                        # Enhanced formatting for booking details
                        if "Booking ID:" in formatted_output:
                            # Split by booking entries and format each one
                            lines = formatted_output.split('\n')
                            enhanced_output = ""
                            current_booking = ""
                            
                            for line in lines:
                                if line.strip().startswith("Booking ID:"):
                                    # Start new booking entry
                                    if current_booking:
                                        enhanced_output += f'<div class="booking-entry">🎫 BOOKING DETAILS:\n{current_booking}</div>\n\n'
                                    current_booking = line + "\n"
                                elif current_booking and line.strip():
                                    # Add to current booking
                                    if "price" in line.lower() or "$" in line:
                                        current_booking += f'💰 {line}\n'
                                    elif "route:" in line.lower():
                                        current_booking += f'🛤️ {line}\n'
                                    elif "time:" in line.lower():
                                        current_booking += f'⏰ {line}\n'
                                    elif "status:" in line.lower():
                                        current_booking += f'✅ {line}\n'
                                    else:
                                        current_booking += f'{line}\n'
                                elif not current_booking and line.strip():
                                    # Regular output (not booking details)
                                    enhanced_output += line + "\n"
                            
                            # Add the last booking if exists
                            if current_booking:
                                enhanced_output += f'<div class="booking-entry">🎫 BOOKING DETAILS:\n{current_booking}</div>\n'
                            
                            st.markdown(f'<div class="repl-output">📊 REPL Result:\n\n{enhanced_output}</div>', unsafe_allow_html=True)
                        else:
                            # Regular formatting for non-booking output
                            st.markdown(f'<div class="repl-output">📊 REPL Result:\n\n{formatted_output}</div>', unsafe_allow_html=True)
                        
                        # Add success indicator
                        st.success("✅ Command executed successfully!")
                    else:
                        st.error("❌ No output generated. Please check your command.")
                
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.markdown(f'<div class="command-input">🔸 Command: {command}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="command-output" style="background: linear-gradient(135deg, #ffebee, #ffcdd2); color: #c62828; border-color: #f44336;">❌ Error: {error_msg}</div>', unsafe_allow_html=True)
                    st.session_state.repl_output.append(f"Command: {command}")
                    st.session_state.repl_output.append(f"Error: {error_msg}")
    
    # Common commands help
    st.markdown("### Common Commands:")
    st.markdown('<div class="info-box">• show bookings of [username]<br>• total price for user [username]<br>• explain booking [booking_id]<br>• show all routes</div>', unsafe_allow_html=True)

def main():
    """Main chatbot application"""
    st.title("🤖 Travel Booking Chatbot")
    
    # Initialize chat if empty
    if not st.session_state.chat_messages:
        welcome_msg = "👋 Hello! Welcome to your Travel Booking Assistant! ✈️\n\nI'm here to help you find and book the perfect tickets for your journey. To get started, just say **'hello'** and I'll guide you through everything!\n\n✨ Ready to explore the world together?"
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome_msg})
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
    
    # Chat input
    user_input = st.chat_input("Type your message here...")
    
    if user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Process and get response
        response = process_booking_chat(user_input)
        
        # Add assistant response
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        
        st.rerun()
    
    # Sidebar with user info and quick actions
    with st.sidebar:
        st.header("Chat Options")
        
        # Login status
        if st.session_state.user_authenticated:
            st.success(f"Logged in as: {st.session_state.current_user}")
            if st.button("Logout"):
                st.session_state.user_authenticated = False
                st.session_state.current_user = None
                st.session_state.current_user_id = None
                st.session_state.booking_context = {}
                st.rerun()
        else:
            st.info("Login to book tickets")
        
        st.divider()
        
        # Quick actions
        st.subheader("Quick Actions")
        if st.button("Show All Routes"):
            st.session_state.chat_messages.append({"role": "user", "content": "show routes"})
            response = process_booking_chat("show routes")
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            st.rerun()
        
        if st.button("Help"):
            st.session_state.chat_messages.append({"role": "user", "content": "help"})
            response = process_booking_chat("help")
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            st.rerun()
        
        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.session_state.booking_context = {}
            st.rerun()

if __name__ == "__main__":
    main()
