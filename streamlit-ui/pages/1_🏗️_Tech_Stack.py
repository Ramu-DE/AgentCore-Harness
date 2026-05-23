"""
Tech Stack & Achievements Dashboard.

Displays the full architecture, AWS services, tools, and features
built in the Returns & Refunds Agent project.
"""

import streamlit as st

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Tech Stack & Achievements", page_icon="🏗️", layout="wide")

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🏗️ Returns & Refunds Agent — Tech Stack & Achievements")
st.markdown(
    "A comprehensive overview of the AI-powered Returns & Refunds Assistant "
    "built with **Strands Agents SDK** and deployed on **AWS Bedrock AgentCore**."
)
st.divider()

# ─── Architecture Overview ────────────────────────────────────────────────────

st.header("📐 Architecture Overview")

st.markdown("""
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Streamlit Chat UI                                │
│                    (Cognito Auth + AgentCore Invoke)                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ invoke_agent_runtime()
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AWS Bedrock AgentCore Runtime                         │
│              ┌─────────────────────────────────────────┐                │
│              │   CustomerAssistantAgent (Strands SDK)   │                │
│              │   • Claude Sonnet 4.5 (Bedrock)         │                │
│              │   • AgentCore Memory (session mgmt)     │                │
│              │   • MCP Client → Gateway                │                │
│              └──────────────────┬──────────────────────┘                │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │ MCP (JSON-RPC over HTTP)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AgentCore MCP Gateway                                 │
│           (OAuth2 via Cognito + Semantic Tool Routing)                   │
│                                                                         │
│   ┌──────────────────────┐       ┌──────────────────────────┐          │
│   │  data-lookup target  │       │  policy-retrieval target  │          │
│   └──────────┬───────────┘       └────────────┬─────────────┘          │
└──────────────┼────────────────────────────────┼─────────────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────┐    ┌────────────────────────────────┐
│   Lambda: data-lookup    │    │   Lambda: policy-retrieval     │
│   • order_lookup         │    │   • Bedrock Knowledge Base     │
│   • user_lookup          │    │   • RAG with country filter    │
│   • product_lookup       │    └────────────────────────────────┘
│   • find_returned        │
│   • process_refund       │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│      Amazon DynamoDB     │
│  • workshop-orders       │
│  • workshop-customers    │
│  • workshop-products     │
└──────────────────────────┘
```
""")

st.divider()

# ─── Core Tech Stack ──────────────────────────────────────────────────────────

st.header("🧰 Core Tech Stack")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🐍 Language & Framework")
    st.markdown("""
    | Component | Technology |
    |-----------|-----------|
    | Language | Python 3.12+ |
    | Agent Framework | Strands Agents SDK |
    | LLM | Claude Sonnet 4.5 |
    | Model Provider | Amazon Bedrock |
    | UI Framework | Streamlit |
    | Deployment CLI | AgentCore CLI |
    """)

with col2:
    st.subheader("☁️ AWS Services")
    st.markdown("""
    | Service | Purpose |
    |---------|---------|
    | Bedrock AgentCore Runtime | Agent hosting & invocation |
    | Bedrock AgentCore Gateway | MCP tool routing |
    | Bedrock AgentCore Memory | Conversation persistence |
    | Bedrock AgentCore Identity | OAuth M2M credentials |
    | Bedrock Knowledge Base | Policy RAG retrieval |
    | Amazon DynamoDB | Order/customer/product data |
    | AWS Lambda | Tool backend functions |
    | Amazon Cognito | User & gateway auth |
    | SSM Parameter Store | Config management |
    | AWS CDK | Infrastructure as Code |
    """)

with col3:
    st.subheader("📦 Key Libraries")
    st.markdown("""
    | Library | Version |
    |---------|---------|
    | `strands-agents` | ≥ 1.13.0 |
    | `strands-agents-tools` | ≥ 0.1.0 |
    | `bedrock-agentcore` | ≥ 1.9.1 |
    | `boto3` / `botocore` | ≥ 1.35.0 |
    | `mcp` | ≥ 1.19.0 |
    | `aws-opentelemetry-distro` | Latest |
    | `streamlit` | ≥ 1.38.0 |
    """)

st.divider()

# ─── Agent Tools ──────────────────────────────────────────────────────────────

st.header("🔧 Agent Tools (MCP Gateway)")

st.markdown("The agent accesses backend tools via the **AgentCore MCP Gateway** using JSON-RPC over HTTP with OAuth2 authentication.")

tool_col1, tool_col2 = st.columns(2)

with tool_col1:
    st.subheader("📊 Data Lookup Tools")
    st.markdown("""
    | Tool | Description |
    |------|-------------|
    | `order_lookup` | Query all orders for a customer by ID |
    | `user_lookup` | Get customer name & country by ID |
    | `product_lookup` | Get product name, category & provider |
    | `find_returned_products` | Find all RETURNED orders (enriched) |
    | `process_refund` | Process refund for a specific order |
    """)
    st.caption("Backend: Lambda → DynamoDB (3 tables)")

with tool_col2:
    st.subheader("📋 Policy Tools")
    st.markdown("""
    | Tool | Description |
    |------|-------------|
    | `policy_retrieval` | RAG retrieval from Knowledge Base |
    """)
    st.markdown("""
    **Features:**
    - Natural language query support
    - Country-based metadata filtering (US, UK, IN, etc.)
    - Relevance scoring for results
    - S3 source attribution
    """)
    st.caption("Backend: Lambda → Bedrock Knowledge Base (retrieve API)")

    st.subheader("⏰ Built-in Tools")
    st.markdown("""
    | Tool | Description |
    |------|-------------|
    | `current_time` | Strands built-in time utility |
    """)

st.divider()

# ─── Features & Achievements ─────────────────────────────────────────────────

st.header("✅ Features & Achievements")

feat_col1, feat_col2 = st.columns(2)

with feat_col1:
    st.subheader("🤖 Agent Capabilities")
    st.markdown("""
    - ✅ Multi-turn conversational AI with streaming responses
    - ✅ Session-based memory persistence (AgentCore Memory)
    - ✅ Dynamic tool discovery via MCP protocol
    - ✅ Semantic tool routing at the gateway level
    - ✅ Knowledge Base RAG for policy documents
    - ✅ Country-specific policy filtering
    - ✅ Order lookup, return eligibility, refund processing
    - ✅ Product & customer enrichment in responses
    """)

    st.subheader("🔐 Security & Auth")
    st.markdown("""
    - ✅ Cognito User Pool for end-user authentication
    - ✅ OAuth2 client_credentials flow for gateway M2M auth
    - ✅ AgentCore Identity credential provider integration
    - ✅ JWT-based gateway authorization (CUSTOM_JWT)
    - ✅ Bearer token injection in MCP transport layer
    - ✅ Token caching with auto-refresh (60s buffer)
    """)

with feat_col2:
    st.subheader("🏗️ Infrastructure & Deployment")
    st.markdown("""
    - ✅ AgentCore CLI deployment (`agentcore deploy`)
    - ✅ CDK-managed infrastructure stack
    - ✅ Multiple runtime configurations (3 runtimes)
    - ✅ Lambda function deployment automation
    - ✅ SSM Parameter Store for config management
    - ✅ Environment variable injection (no shell placeholders)
    - ✅ Public network mode for runtime access
    """)

    st.subheader("🖥️ User Interface")
    st.markdown("""
    - ✅ Streamlit chat UI with real-time agent responses
    - ✅ Cognito login flow (USER_PASSWORD_AUTH)
    - ✅ NEW_PASSWORD_REQUIRED challenge handling
    - ✅ Session management with unique IDs
    - ✅ Chat history persistence in session state
    - ✅ Logout & session reset
    """)

    st.subheader("🧪 Testing & Validation")
    st.markdown("""
    - ✅ Gateway connectivity test script (MCP tools/list)
    - ✅ AgentCore CLI invoke (non-interactive mode)
    - ✅ Local dev mode (`agentcore dev`)
    - ✅ OpenTelemetry tracing integration
    """)

st.divider()

# ─── Runtimes Deployed ────────────────────────────────────────────────────────

st.header("🚀 Deployed Runtimes")

runtime_data = [
    {
        "Runtime": "CustomerAssistantAgent",
        "Purpose": "Production agent with full MCP gateway + Memory",
        "Auth": "OAuth2 (client_credentials via env vars)",
        "Memory": "✅ AgentCore Memory",
        "Python": "3.14",
    },
    {
        "Runtime": "CustAssistantHarness",
        "Purpose": "Harness variant using AgentCore Identity for OAuth",
        "Auth": "AgentCore Identity (M2M)",
        "Memory": "✅ AgentCore Memory",
        "Python": "3.14",
    },
    {
        "Runtime": "AgentCoreProject",
        "Purpose": "Base/default runtime (simple assistant)",
        "Auth": "None (no gateway)",
        "Memory": "❌",
        "Python": "3.14",
    },
]

st.table(runtime_data)

st.divider()

# ─── Data Model ───────────────────────────────────────────────────────────────

st.header("🗄️ Data Model (DynamoDB)")

db_col1, db_col2, db_col3 = st.columns(3)

with db_col1:
    st.subheader("workshop-orders")
    st.markdown("""
    | Field | Type |
    |-------|------|
    | `customer_id` (PK) | String |
    | `product_id` (SK) | String |
    | `purchased_date` | String |
    | `status` | String |
    """)
    st.caption("Statuses: DELIVERED, OPENED, SHIPPED, RETURNED, REFUNDED")

with db_col2:
    st.subheader("workshop-customers")
    st.markdown("""
    | Field | Type |
    |-------|------|
    | `customer_id` (PK) | String |
    | `name` | String |
    | `country_code` | String |
    """)
    st.caption("Example: C-01 → Rajesh Kumar (IN)")

with db_col3:
    st.subheader("workshop-products")
    st.markdown("""
    | Field | Type |
    |-------|------|
    | `product_id` (PK) | String |
    | `product_name` | String |
    | `product_category` | String |
    | `provider` | String |
    """)
    st.caption("Example: P-001 → Electronics category")

st.divider()

# ─── Project Stats ────────────────────────────────────────────────────────────

st.header("📈 Project Stats")

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

with stat_col1:
    st.metric("AWS Services", "10", help="Bedrock, AgentCore, DynamoDB, Lambda, Cognito, SSM, CDK, S3, IAM, CloudWatch")

with stat_col2:
    st.metric("Agent Tools", "7", help="6 MCP gateway tools + 1 built-in")

with stat_col3:
    st.metric("Runtimes Deployed", "3", help="CustomerAssistantAgent, CustAssistantHarness, AgentCoreProject")

with stat_col4:
    st.metric("Lambda Functions", "2", help="data-lookup, policy-retrieval")

stat_col5, stat_col6, stat_col7, stat_col8 = st.columns(4)

with stat_col5:
    st.metric("DynamoDB Tables", "3", help="orders, customers, products")

with stat_col6:
    st.metric("Auth Flows", "2", help="USER_PASSWORD_AUTH + client_credentials")

with stat_col7:
    st.metric("MCP Protocol", "✅", help="JSON-RPC over Streamable HTTP")

with stat_col8:
    st.metric("Memory", "✅", help="AgentCore Memory with session persistence")

st.divider()

# ─── How It Works ─────────────────────────────────────────────────────────────

st.header("🔄 How It Works — Request Flow")

st.markdown("""
1. **User** types a message in the Streamlit chat UI
2. **Streamlit** authenticates via Cognito and calls `invoke_agent_runtime()` with the prompt
3. **AgentCore Runtime** routes to the `CustomerAssistantAgent` runtime
4. **Strands Agent** (Claude Sonnet 4.5) processes the prompt with its system prompt and tools
5. **Agent** decides which tools to call based on the user's intent
6. **MCP Client** sends JSON-RPC requests to the **AgentCore Gateway** (with OAuth Bearer token)
7. **Gateway** routes tool calls to the appropriate **Lambda function** target
8. **Lambda** queries **DynamoDB** (data) or **Bedrock Knowledge Base** (policies)
9. **Results** flow back through the MCP protocol to the agent
10. **Agent** synthesizes a natural language response and streams it back
11. **AgentCore Memory** persists the conversation for session continuity
""")

st.divider()

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown(
    "---\n"
    "Built with ❤️ using **Strands Agents SDK** + **AWS Bedrock AgentCore** | "
    "Region: `us-west-2` | Model: `Claude Sonnet 4.5`"
)
