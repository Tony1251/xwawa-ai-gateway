# xwawa-langchain

LangChain integration for xwawa-ai-gateway.

```python
from xwawa_langchain import XwawaChatLLM

llm = XwawaChatLLM(api_key="your-key")
response = llm.invoke([HumanMessage(content="Hello")])
```
