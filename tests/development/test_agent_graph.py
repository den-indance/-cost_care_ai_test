from IPython.display import Image, display

from agent.graph import create_agent_graph


def test_create_agent_graph():
    print("🧪 Testing graph creation...")

    try:
        create_agent_graph()
        print("✅ Graph created successfully!")
        print("\nGraph structure:")
        print("- Entry: router")
        print("- Nodes: router, rag_qa, qualification, parse_info, slot_proposal, confirmation, booking")
        print("- Exits: rag_qa → END, booking → END")

    except Exception as e:
        print(f"❌ Error creating graph: {e}")


# todo test this
def visualize_graph():
    try:
        app = create_agent_graph()
        display(Image(app.get_graph().draw_mermaid_png()))
    except ImportError:
        print("Install pygraphviz and IPython to visualize the graph")
