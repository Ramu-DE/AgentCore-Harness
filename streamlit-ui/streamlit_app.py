"""
Streamlit Chat UI for the Returns & Refunds Assistant.

Authenticates users via Cognito and invokes the deployed AgentCore Runtime agent.
"""

import json
import uuid

import boto3
import streamlit as st

# ─── Configuration ────────────────────────────────────────────────────────────

AWS_REGION = "us-west-2"

# Cognito settings — from the project's cognito_config.json
COGNITO_USER_POOL_ID = "us-west-2_JqFdaft8o"
COGNITO_APP_CLIENT_ID = "4sa8r95nqmfpsd1dltmbodcq5o"

# AgentCore Runtime ARN — from deployed-state.json
AGENT_RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-west-2:817509234255:"
    "runtime/AgentCoreProject_CustomerAssistantAgent-S6e26GCfky"
)

# Default credentials for workshop convenience
DEFAULT_USERNAME = "administrator@example.com"
DEFAULT_PASSWORD = "Workshop1!"

WELCOME_MESSAGE = (
    "Hello! I'm your Returns & Refunds Assistant. I can help you look up orders, "
    "check return eligibility, calculate refunds and answer policy questions. "
    "How can I help you today?"
)

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Returns & Refunds Assistant", page_icon="🔄")


# ─── Session State Initialization ────────────────────────────────────────────

def init_session_state() -> None:
    """Initialize all session state keys with defaults."""
    defaults = {
        "authenticated": False,
        "id_token": None,
        "access_token": None,
        "refresh_token": None,
        "user_email": None,
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "challenge_session": None,
        "challenge_name": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ─── Authentication ───────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> bool:
    """Authenticate user via Cognito USER_PASSWORD_AUTH flow.

    Returns True on success, sets session state on challenge.
    """
    client = boto3.client("cognito-idp", region_name=AWS_REGION)

    try:
        response = client.initiate_auth(
            ClientId=COGNITO_APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            },
        )
    except client.exceptions.NotAuthorizedException:
        st.error("Invalid email or password.")
        return False
    except client.exceptions.UserNotFoundException:
        st.error("User not found.")
        return False
    except Exception as e:
        st.error(f"Authentication failed: {e}")
        return False

    # Handle NEW_PASSWORD_REQUIRED challenge (first-time login)
    if "ChallengeName" in response:
        if response["ChallengeName"] == "NEW_PASSWORD_REQUIRED":
            st.session_state["challenge_session"] = response["Session"]
            st.session_state["challenge_name"] = "NEW_PASSWORD_REQUIRED"
            return False

    # Successful auth — store tokens
    auth_result = response["AuthenticationResult"]
    st.session_state["authenticated"] = True
    st.session_state["id_token"] = auth_result.get("IdToken")
    st.session_state["access_token"] = auth_result.get("AccessToken")
    st.session_state["refresh_token"] = auth_result.get("RefreshToken")
    st.session_state["user_email"] = username
    return True


def respond_to_new_password_challenge(username: str, new_password: str) -> bool:
    """Complete the NEW_PASSWORD_REQUIRED challenge."""
    client = boto3.client("cognito-idp", region_name=AWS_REGION)

    try:
        response = client.respond_to_auth_challenge(
            ClientId=COGNITO_APP_CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=st.session_state["challenge_session"],
            ChallengeResponses={
                "USERNAME": username,
                "NEW_PASSWORD": new_password,
            },
        )
    except Exception as e:
        st.error(f"Failed to set new password: {e}")
        return False

    # Store tokens after successful challenge response
    auth_result = response["AuthenticationResult"]
    st.session_state["authenticated"] = True
    st.session_state["id_token"] = auth_result.get("IdToken")
    st.session_state["access_token"] = auth_result.get("AccessToken")
    st.session_state["refresh_token"] = auth_result.get("RefreshToken")
    st.session_state["user_email"] = username
    st.session_state["challenge_session"] = None
    st.session_state["challenge_name"] = None
    return True


def logout() -> None:
    """Clear authentication state."""
    for key in ["authenticated", "id_token", "access_token", "refresh_token",
                "user_email", "messages", "challenge_session", "challenge_name"]:
        st.session_state[key] = None
    st.session_state["authenticated"] = False
    st.session_state["messages"] = []
    st.session_state["session_id"] = str(uuid.uuid4())


# ─── Agent Invocation ─────────────────────────────────────────────────────────

def invoke_agent(prompt: str) -> str:
    """Invoke the deployed AgentCore Runtime agent and return the streamed response."""
    # Derive actor_id from email (part before @)
    actor_id = st.session_state["user_email"].split("@")[0]

    # Build the payload matching the agent's expected format
    payload = json.dumps({
        "prompt": prompt,
        "session_id": st.session_state["session_id"],
        "actor_id": actor_id,
    }).encode()

    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=st.session_state["session_id"],
            payload=payload,
        )
    except Exception as e:
        return f"⚠️ Failed to invoke agent: {e}"

    # Process the streaming response
    content_type = response.get("contentType", "")
    content_parts = []

    try:
        if "text/event-stream" in content_type:
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        chunk = decoded[6:]
                        # Try to parse as JSON; if successful yield parsed value
                        try:
                            parsed = json.loads(chunk)
                            content_parts.append(str(parsed))
                        except (json.JSONDecodeError, ValueError):
                            content_parts.append(chunk)
        elif content_type == "application/json":
            raw_parts = []
            for chunk in response.get("response", []):
                raw_parts.append(chunk.decode("utf-8"))
            result = json.loads("".join(raw_parts))
            content_parts.append(str(result))
        else:
            # Fallback: read raw response body
            for chunk in response.get("response", []):
                decoded = chunk.decode("utf-8")
                try:
                    parsed = json.loads(decoded)
                    content_parts.append(str(parsed))
                except (json.JSONDecodeError, ValueError):
                    content_parts.append(decoded)
    except Exception as e:
        return f"⚠️ Error reading agent response: {e}"

    return "".join(content_parts) if content_parts else "No response from agent."


# ─── UI Rendering ─────────────────────────────────────────────────────────────

def render_login_page() -> None:
    """Render the login form or new-password challenge form."""
    st.title("🔄 Returns & Refunds Assistant")
    st.markdown("Please log in to continue.")

    # Handle NEW_PASSWORD_REQUIRED challenge
    if st.session_state.get("challenge_name") == "NEW_PASSWORD_REQUIRED":
        st.warning("You must set a new password before continuing.")
        with st.form("new_password_form"):
            new_password = st.text_input("New Password", type="password")
            submitted = st.form_submit_button("Set New Password")
            if submitted and new_password:
                if respond_to_new_password_challenge(DEFAULT_USERNAME, new_password):
                    st.rerun()
        return

    # Standard login form
    with st.form("login_form"):
        email = st.text_input("Email", value=DEFAULT_USERNAME)
        password = st.text_input("Password", value=DEFAULT_PASSWORD, type="password")
        submitted = st.form_submit_button("Log In")

        if submitted:
            if authenticate(email, password):
                st.rerun()


def render_sidebar() -> None:
    """Render the sidebar with user info and logout."""
    with st.sidebar:
        st.markdown("### 👤 User Info")
        st.markdown(f"**Email:** {st.session_state['user_email']}")
        st.markdown(f"**Session:** `{st.session_state['session_id'][:8]}...`")
        st.divider()
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()


def render_chat() -> None:
    """Render the chat interface."""
    st.title("🔄 Returns & Refunds Assistant")

    # Show welcome message if chat is empty
    if not st.session_state["messages"]:
        st.session_state["messages"].append({
            "role": "assistant",
            "content": WELCOME_MESSAGE,
        })

    # Display chat history
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Type your message..."):
        # Add user message to history and display it
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Invoke agent and display response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = invoke_agent(prompt)
            st.markdown(response)

        # Add assistant response to history
        st.session_state["messages"].append({"role": "assistant", "content": response})


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Main application entry point."""
    if st.session_state["authenticated"]:
        render_sidebar()
        render_chat()
    else:
        render_login_page()


if __name__ == "__main__":
    main()
