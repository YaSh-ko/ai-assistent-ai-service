#!/usr/bin/env python3
"""
Manual Test Script for Neo4j Integration
This script provides an interactive way to test the Neo4j integration
and demonstrate the full workflow of the knowledge graph system.
"""

import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
from app.factory.database_factory import DatabaseFactory


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_step(step_num, description):
    """Print a step description."""
    print(f"\n[Step {step_num}] {description}")
    print("-" * 80)


def print_result(data, indent=2):
    """Print result data in a readable format."""
    import json
    indent_str = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{indent_str}{key}:")
                print_result(value, indent + 2)
            else:
                print(f"{indent_str}{key}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            print(f"{indent_str}[{i}]")
            print_result(item, indent + 2)
    else:
        print(f"{indent_str}{data}")


async def main():
    print_header("Neo4j Integration Manual Test")
    print("\nThis script will demonstrate the full Neo4j integration workflow.")
    print("It will create nodes, relationships, and run queries to show the capabilities.")
    
    input("\nPress Enter to start...")
    
    try:
        # Step 1: Initialize
        print_step(1, "Initializing  Database Factory and GraphRepository")
        graph_repo = await DatabaseFactory.create_graph_repository()
        print("✓ GraphRepository created successfully")
        print("  - Neo4j provider initialized with singleton pattern")
        print("  - Health check passed")
        print("  - All repositories loaded")
        
        # User ID for this demo
        user_id = "demo_user_manual_test"
        timestamp = datetime.now()
        
        # Step 2: Create Nodes
        print_step(2, "Creating Knowledge Graph Nodes")
        
        # Create Entry
        entry_id = "demo_entry_1"
        print(f"\nCreating Entry: {entry_id}")
        await graph_repo.entries.create_entry(
            entry_id=entry_id,
            user_id=user_id,
            session_id="demo_session",
            timestamp=timestamp,
            content="Today I realized that procrastination might be a defense mechanism rather than laziness.",
            content_summary="Insight about procrastination",
            sentiment_score=0.3
        )
        print("✓ Entry created")
        
        # Create Concepts
        concept1_id = "concept_procrastination_v1"
        concept2_id = "concept_procrastination_v2"
        
        print(f"\nCreating Concept 1: {concept1_id}")
        await graph_repo.concepts.create_concept(
            concept_id=concept1_id,
            name="Procrastination as laziness",
            user_id=user_id,
            description="Initial understanding of procrastination",
            relevance=0.5
        )
        print("✓ Concept 1 created")
        
        print(f"\nCreating Concept 2: {concept2_id}")
        await graph_repo.concepts.create_concept(
            concept_id=concept2_id,
            name="Procrastination as defense",
            user_id=user_id,
            description="Evolved understanding - protection from fear",
            relevance=0.9
        )
        print("✓ Concept 2 created")
        
        # Create Affect
        affect_id = "affect_anxiety"
        print(f"\nCreating Affect: {affect_id}")
        await graph_repo.affects.create_affect(
            affect_id=affect_id,
            name="Anxiety",
            user_id=user_id,
            valence=-0.5,
            arousal=0.7,
            description="Feeling of worry and unease"
        )
        print("✓ Affect created")
        
        # Create Goal
        goal_id = "goal_overcome_proc"
        print(f"\nCreating Goal: {goal_id}")
        await graph_repo.goals.create_goal(
            goal_id=goal_id,
            title="Overcome procrastination",
            user_id=user_id,
            status="active",
            priority="high",
            description="Work on reducing procrastination patterns"
        )
        print("✓ Goal created")
        
        # Create Experiment
        experiment_id = "exp_pomodoro"
        print(f"\nCreating Experiment: {experiment_id}")
        await graph_repo.experiments.create_experiment(
            experiment_id=experiment_id,
            title="Pomodoro Technique Trial",
            user_id=user_id,
            status="active",
            description="Testing if short work intervals reduce procrastination",
            started_at=timestamp
        )
        print("✓ Experiment created")
        
        # Step 3: Create Relationships
        print_step(3, "Creating Relationships Between Nodes")
        
        print("\nLinking Entry → Concept (MENTIONS)")
        await graph_repo.entry_links.link_to_concept(
            entry_id, concept2_id, 
            "Realized it's not just laziness", 
            0.9
        )
        print("✓ Relationship created")
        
        print("\nLinking Entry → Affect (EXPRESSES)")
        await graph_repo.entry_links.link_to_affect(
            entry_id, affect_id,
            0.6,
            "Feeling anxious about procrastinating"
        )
        print("✓ Relationship created")
        
        print("\nLinking Entry → Goal (RELATES_TO)")
        await graph_repo.entry_links.link_to_goal(
            entry_id, goal_id,
            "reflection", 0.7,
            "Thinking about why I procrastinate"
        )
        print("✓ Relationship created")
        
        print("\nLinking Entry → Experiment (DOCUMENTS)")
        await graph_repo.entry_links.link_to_experiment(
            entry_id, experiment_id,
            1, "Day 1: Started using pomodoro", 0.5
        )
        print("✓ Relationship created")
        
        print("\nLinking Concept 1 → Concept 2 (EVOLVES_INTO)")
        await graph_repo.concept_links.link_evolution(
            concept1_id, concept2_id,
            "refinement",
            description="Deeper understanding emerged"
        )
        print("✓ Evolution relationship created")
        
        print("\nLinking Goal → Concept (BASED_ON)")
        await graph_repo.goal_links.link_to_concept(
            goal_id, concept2_id, 0.9
        )
        print("✓ Relationship created")
        
        print("\nLinking Experiment → Concept (TESTS)")
        await graph_repo.experiment_links.link_to_concept(
            experiment_id, concept2_id, 0.8, "pending"
        )
        print("✓ Test relationship created")
        
        # Step 4: Query the Graph
        print_step(4, "Querying the Knowledge Graph")
        
        print("\nQuerying: Get User Graph Summary")
        summary = await graph_repo.get_user_graph_summary(user_id)
        print_result(summary)
        
        print("\nQuerying: Find Entries Mentioning Concept")
        entries = await graph_repo.entry_links.find_by_concept(concept2_id, user_id)
        print(f"Found {len(entries)} entries mentioning the concept")
        
        print("\nQuerying: Get Goal Progress Chain")
        progress = await graph_repo.entry_links.get_goal_progress_chain(goal_id)
        print(f"Found {len(progress)} progress entries for the goal")
        
        print("\nQuerying: Get Concept Evolution Chain")
        evolution = await graph_repo.concept_links.get_evolution_chain(concept1_id, user_id)
        print(f"Found {len(evolution)} evolved concepts in the chain")
        
        print("\nQuerying: Get Experiment Journal")
        journal = await graph_repo.entry_links.get_experiment_journal(experiment_id)
        print(f"Found {len(journal)} journal entries for the experiment")
        
        print("\nQuerying: Find All Connections (depth=2)")
        connections = await graph_repo.queries.find_all_connections(entry_id, depth=2)
        print(f"Found {len(connections)} connected nodes within 2 hops")
        
        # Step 5: Cleanup
        print_step(5, "Cleanup Test Data")
        
        print("\nDeleting all test nodes...")
        deleted_count = 0
        
        await graph_repo.entries.delete_entry(entry_id)
        deleted_count += 1
        
        await graph_repo.concepts.delete_concept(concept1_id)
        await graph_repo.concepts.delete_concept(concept2_id)
        deleted_count += 2
        
        await graph_repo.affects.delete_affect(affect_id)
        deleted_count += 1
        
        await graph_repo.goals.delete_goal(goal_id)
        deleted_count += 1
        
        await graph_repo.experiments.delete_experiment(experiment_id)
        deleted_count += 1
        
        print(f"✓ Deleted {deleted_count} test nodes")
        print("  (All relationships were automatically deleted via DETACH DELETE)")
        
        # Final Summary
        print_header("Test Complete!")
        print("\n✅ All operations completed successfully!")
        print("\nWhat was demonstrated:")
        print("  1. Database Factory initialization with singleton pattern")
        print("  2. Creating all types of nodes (Entry, Concept, Affect, Goal, Experiment)")
        print("  3. Creating various relationship types")
        print("  4. Querying the knowledge graph (simple and complex queries)")
        print("  5. Proper cleanup with cascade delete")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        print("\nClosing database connection...")
        await DatabaseFactory.close_graph_database()
        print("✓ Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
