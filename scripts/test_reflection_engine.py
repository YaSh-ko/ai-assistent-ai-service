#!/usr/bin/env python3
"""
Test script for Reflection/Critic Loops reasoning engine.
Tests the new reflection engine with a sample query.
"""

import asyncio
import sys
import os
import logging

# Clear GIGACHAT_CREDENTIALS to avoid auth issues
os.environ.pop('GIGACHAT_CREDENTIALS', None)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.factory.reasoning_factory import ReasoningFactory
from app.core.config import settings

logger = logging.getLogger(__name__)


async def test_reflection_engine():
    """Test the reflection reasoning engine."""
    
    print("=" * 60)
    print("Testing Reflection/Critic Loops Reasoning Engine")
    print("=" * 60)
    print()
    
    # Configuration
    print("Configuration:")
    print(f"Current Model: {settings.CURRENT_MODEL}")
    print(f"Max Iterations: {settings.REFLECTION_CONFIG['max_iterations']}")
    print(f"Quality Threshold: {settings.REFLECTION_CONFIG['quality_threshold']}")
    print(f"Critique Temperature: {settings.REFLECTION_CONFIG['critique_temperature']}")
    print(f"Refinement Temperature: {settings.REFLECTION_CONFIG['refinement_temperature']}")
    print()
    
    try:
        # Get reflection engine
        print("Initializing reflection engine...")
        engine = ReasoningFactory.get_reasoning_engine("reflection")
        print("✓ Engine initialized")
        print()
        
        # Test query
        test_query = "Объясни концепцию машинного обучения простыми словами"
        print(f"Test Query: {test_query}")
        print()
        
        # Execute reasoning
        print("Executing reflection reasoning...")
        print("-" * 60)
        result = await engine.reason(test_query)
        print("-" * 60)
        print()
        
        # Display results
        print("RESULTS:")
        print("=" * 60)
        print()
        
        print("Final Answer:")
        print(result["answer"] if result["answer"] else "No answer (error occurred)")
        print()
        
        print(f"Status: {result['status']}")
        print(f"Total Duration: {result['total_duration_ms']:.2f}ms")
        if result.get("error"):
            print(f"Error: {result['error']}")
        print()
        
        # Display reasoning steps
        print("Reasoning Steps:")
        print("-" * 60)
        steps = engine.get_reasoning_steps()
        for i, step in enumerate(steps, 1):
            print(f"\nStep {i}: {step['description']}")
            print(f"  Action: {step['action']}")
            print(f"  Duration: {step['duration_ms']:.2f}ms")
            if step.get("metadata") and step["metadata"] and "quality_score" in step["metadata"]:
                print(f"  Quality Score: {step['metadata']['quality_score']:.2f}")
            print(f"  Observation: {step['observation'][:200]}...")
        print()
        
        # Display metadata
        metadata = engine.get_metadata()
        print("Engine Metadata:")
        print(f"  Engine Type: {metadata['engine_type']}")
        print(f"  Total Steps: {metadata['total_steps']}")
        print(f"  Max Iterations: {metadata['max_iterations']}")
        print(f"  Quality Threshold: {metadata['quality_threshold']}")
        print()
        
        print("=" * 60)
        print("✓ Test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        logger.exception("Test failed")
        return False
    
    finally:
        # Clean up: close all model providers
        from app.factory.model_factory import ModelFactory
        await ModelFactory.close_all()
        print("\n✓ Resources cleaned up")


async def main():
    """Main entry point."""
    success = await test_reflection_engine()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
