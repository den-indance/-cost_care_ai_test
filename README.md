```
+-------------------------------------------------------+
|                 USER (CLI / Frontend)                 |
+--------------------------+----------------------------+
                           |
                           v
+-------------------------------------------------------+
|            LANGGRAPH AGENT (State Machine)            |
|                                                       |
|  +-------------------------------------------------+  |
|  |                  ROUTER NODE                    |  |
|  |      (Intent: Q&A Path vs. Booking Path)        |  |
|  +------------+-------------------------+----------+  |
|               |                         |             |
|        [ RAG FLOW ]              [ BOOKING FSM ]      |
|               v                         v             |
|  +-----------------------+   +---------------------+  |
|  |     rag_qa_node       |   | 1. qualification    |  |
|  |   - Vector Search     |   | 2. parse_user_info  |  |
|  |   - LLM Answer        |   | 3. slot_proposal    |  |
|  |                       |   | 4. confirmation     |  |
|  |         DONE          |   | 5. booking_node     |  |
|  +-----------------------+   +---------------------+  |
|                                                       |
+-------+------------------+--------------------+-------+
        |                  |                    |
        v                  v                    v
+---------------+  +---------------+  +-----------------+
|  RAG SERVICE  |  |  LLM SERVICE  |  |  CALENDAR API   |
| (ChromaDB API)|  |   (Gemini)    |  | (Google OAuth)  |
+-------+-------+  +-------+-------+  +--------+--------+
        |                  |                   |
        v                  v                   v
 [Local Vector DB]  [Reasoning/JSON]    [Google Calendar]
+-------------------------------------------------------+
```

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



*how to start local development:*

    1) create docker network: docker network create cost_care_ai_test
    2) create proejct at the google console and add google_creds.json file at the config dir


*added https://smith.langchain.com for the project llm observability*
![smith.png](data%2Fsmith.png)