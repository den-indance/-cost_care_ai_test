+---------------------------------------------------------------+
|                   USER (CLI Interface)                        |
+-------------------------------+-------------------------------+
                                |
                                v
+---------------------------------------------------------------+
|              LangGraph Agent (State Machine)                  |
|                                                               |
|  +--------------------------------------------------------+   |
|  |  Router Node                                           |   |
|  |  (Intent Classification: RAG vs Booking)              |   |
|  +------------+-------------------------+-----------------+   |
|               |                         |                     |
|               v                         v                     |
|  +----------------------+  +-------------------------------+  |
|  |   RAG Path           |  |   Booking Path                |  |
|  |   (Q&A Flow)         |  |   (FSM: 6 nodes)              |  |
|  |                      |  |                               |  |
|  |  1. rag_qa_node      |  |  1. qualification_node        |  |
|  |     - Search KB      |  |  2. parse_user_info_node      |  |
|  |     - LLM answer     |  |  3. slot_proposal_node        |  |
|  |     - Done           |  |  4. confirmation_node         |  |
|  |                      |  |  5. booking_node              |  |
|  +----------------------+  +-------------------------------+  |
|                                                               |
+---------------------------------------------------------------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
        v                       v                       v
+---------------+       +---------------+       +------------------+
| RAG Service   |       |  LLM (Gemini) |       | Calendar Service |
|               |       |               |       |                  |
| - Vector DB   |       | - Text Gen    |       | - OAuth 2.0      |
| - Embeddings  |       | - Extraction  |       | - Freebusy API   |
| - Search      |       | - Reasoning   |       | - Events API     |
+-------+-------+       +---------------+       +--------+---------+
        |                                                |
        v                                                v
+---------------+                              +-------------------+
|  Chroma DB    |                              | Google Calendar   |
|  (Local)      |                              | API               |
+---------------+                              +-------------------+



🛠 Development Commands

Use the following make commands to manage the project environment:

    Run Unit Tests:

    make unittests — Executes the test suite to ensure everything is working as expected.

    Format Code:

    make format — Automatically formats the code to match the project's style standards.

    Environment Shell:

    make bash — Opens an interactive bash session inside the development container.

    Run CLI:

    make run_conversation — Launches the command-line interface for interaction.

⚠️ System Compatibility

The current Makefile and Docker image are specifically tailored for Linux (Ubuntu) environments.

If you are running this on other operating systems (such as macOS or Windows/WSL), you may need to manually adjust the configuration files to ensure proper volume mounting and performance.
