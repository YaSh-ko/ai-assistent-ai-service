# Reflection/Critic Loops Reasoning Engine

## Overview

The Reflection/Critic Loops reasoning engine implements an iterative self-improvement pattern where the AI:
1. Generates an initial answer
2. Critiques its own answer
3. Evaluates the quality
4. Refines the answer based on critique
5. Repeats until quality threshold is met or max iterations reached

## Architecture

### Components

- **ReflectionReasoning** (`app/reasoning/reflection_reasoning.py`): Core reasoning engine
- **ReflectionProvider** (`app/providers/reasoning/reflection_provider.py`): Provider wrapper
- **ReasoningFactory** (`app/factory/reasoning_factory.py`): Factory for creating reasoning engines

### Configuration

Configuration is defined in `app/core/config.py` and can be overridden via environment variables:

```python
REFLECTION_CONFIG = {
    "max_iterations": 3,           # Maximum reflection loops
    "quality_threshold": 0.8,      # Stop if quality >= threshold
    "critique_temperature": 0.3,   # Temperature for critique (lower = more focused)
    "refinement_temperature": 0.7  # Temperature for refinement (higher = more creative)
}
```

### Environment Variables

Add to `.env`:

```bash
# Reflection/Critic Loops Configuration
REFLECTION_MAX_ITERATIONS=3
REFLECTION_QUALITY_THRESHOLD=0.8
REFLECTION_CRITIQUE_TEMP=0.3
REFLECTION_REFINEMENT_TEMP=0.7

# Set as default reasoning engine (optional)
DEFAULT_REASONING_ENGINE=reflection
```

## Usage

### Via Factory

```python
from app.factory.reasoning_factory import ReasoningFactory
from app.factory.model_factory import ModelFactory

# Get reflection engine
engine = ReasoningFactory.get_reasoning_engine("reflection")

# Execute reasoning
result = await engine.reason("Explain machine learning in simple terms")

# Access results
print(result["answer"])
print(f"Status: {result['status']}")
print(f"Duration: {result['total_duration_ms']}ms")

# Get reasoning steps
steps = engine.get_reasoning_steps()
for step in steps:
    print(f"{step['description']}: {step['action']}")

# IMPORTANT: Always clean up resources
await ModelFactory.close_all()
```

### Proper Resource Cleanup

Always close model providers to avoid resource leaks:

```python
async def my_function():
    try:
        engine = ReasoningFactory.get_reasoning_engine("reflection")
        result = await engine.reason("Your query")
        return result
    finally:
        # Clean up HTTP sessions and connections
        from app.factory.model_factory import ModelFactory
        await ModelFactory.close_all()
```

### Via API

The reflection engine can be used through the chat API by setting the reasoning engine parameter:

```bash
curl -X POST http://localhost:8001/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "reasoning_engine": "reflection"
  }'
```

## Testing

### Quick Test

Run the test script to verify the reflection engine:

```bash
python3 scripts/test_reflection_engine.py
```

### Expected Output

The test will:
1. Initialize the reflection engine
2. Execute reasoning on a test query
3. Display the final answer
4. Show all reasoning steps with quality scores
5. Display engine metadata

Example output:
```
✓ Engine initialized
Test Query: Объясни концепцию машинного обучения простыми словами

Reasoning Steps:
Step 1: Generate initial answer (10.2s)
Step 2: Critique answer (iteration 1) (14.5s)
Step 3: Evaluate quality (iteration 1) - Quality Score: 0.65
Step 4: Refine answer (iteration 1) (16.0s)
Step 5: Critique answer (iteration 2) (12.3s)
Step 6: Evaluate quality (iteration 2) - Quality Score: 0.85
Quality threshold met: 0.85 >= 0.8

✓ Test completed successfully!
```

## How It Works

### Reflection Loop

1. **Initial Generation**: Creates first draft answer using refinement temperature
2. **Critique**: Analyzes answer for accuracy, completeness, clarity, and relevance using critique temperature
3. **Quality Evaluation**: Scores answer quality (0.0-1.0) based on critique
4. **Refinement**: Improves answer based on critique feedback
5. **Iteration**: Repeats steps 2-4 until quality threshold met or max iterations reached

### Quality Scoring

The engine uses the LLM to evaluate answer quality on a scale of 0.0 to 1.0:
- **0.0-0.4**: Poor quality, needs significant improvement
- **0.5-0.7**: Moderate quality, some improvements needed
- **0.8-1.0**: High quality, meets standards

### Temperature Settings

- **Critique Temperature (0.3)**: Lower temperature for focused, consistent critique
- **Refinement Temperature (0.7)**: Higher temperature for creative improvements

## Advantages

1. **Self-Improving**: Automatically refines answers through iteration
2. **Quality-Aware**: Stops when quality threshold is met
3. **Transparent**: All reasoning steps are logged and accessible
4. **Configurable**: Adjustable iterations, thresholds, and temperatures

## Limitations

1. **Slower**: Multiple LLM calls per query (typically 4-6 calls)
2. **Token Usage**: Higher token consumption due to multiple iterations
3. **Cost**: More expensive than single-pass reasoning
4. **Convergence**: May not always reach quality threshold within max iterations

## Comparison with CoT

| Feature | Reflection | Chain-of-Thought |
|---------|-----------|------------------|
| Iterations | Multiple (3+) | Single pass |
| Self-Critique | Yes | No |
| Quality Scoring | Yes | No |
| Speed | Slower | Faster |
| Token Usage | Higher | Lower |
| Answer Quality | Higher (iterative improvement) | Good (single pass) |

## Best Use Cases

- Complex questions requiring thorough analysis
- Tasks where answer quality is critical
- Situations where multiple perspectives are valuable
- Educational content generation
- Technical documentation

## Files Modified/Created

### Created
- `app/reasoning/reflection_reasoning.py` - Core reasoning engine
- `app/providers/reasoning/reflection_provider.py` - Provider wrapper
- `scripts/test_reflection_engine.py` - Test script
- `docs/REFLECTION_REASONING_ENGINE.md` - This documentation

### Modified
- `app/factory/reasoning_factory.py` - Added reflection engine case
- `app/core/config.py` - Added REFLECTION_CONFIG
- `.env` - Added reflection configuration variables

## Future Enhancements

1. **Adaptive Iterations**: Dynamically adjust max iterations based on complexity
2. **Multi-Critic**: Use multiple critique perspectives
3. **Parallel Refinement**: Generate multiple refinements and select best
4. **Learning from History**: Use past critiques to improve future answers
5. **Custom Quality Metrics**: Allow domain-specific quality evaluation
