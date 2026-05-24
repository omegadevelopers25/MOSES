from groq import Groq
from typing import Generator, Optional

# Lazily create the Groq client so importing this module does not require
# a GROQ_API_KEY to be present at import time.
_client: Groq | None = None


def _get_client() -> Groq:
  global _client
  if _client is None:
    _client = Groq()
  return _client


def generate(
  prompt: str,
  model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
  stream: bool = False,
  temperature: float = 1.0,
  max_completion_tokens: int = 1024,
  top_p: float = 1.0,
  stop: Optional[str] = None,
) -> Optional[Generator[str, None, None]]:
  """Generate text using the Groq client.

  If `stream` is True this returns a generator yielding chunks of text.
  Otherwise it returns a single string result.
  """
  messages = [{"role": "user", "content": prompt}]
  client = _get_client()

  if stream:
    completion = client.chat.completions.create(
      model=model,
      messages=messages,
      temperature=temperature,
      max_completion_tokens=max_completion_tokens,
      top_p=top_p,
      stream=True,
      stop=stop,
    )

    def _iter():
      for chunk in completion:
        yield chunk.choices[0].delta.content or ""

    return _iter()

  # Non-streaming: call the API synchronously and return a string result.
  completion = client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=temperature,
    max_completion_tokens=max_completion_tokens,
    top_p=top_p,
    stream=False,
    stop=stop,
  )

  try:
    return "".join(chunk.choices[0].delta.content or "" for chunk in completion)
  except TypeError:
    try:
      return completion.choices[0].message.content  # type: ignore[attr-defined]
    except Exception:
      return str(completion)


if __name__ == "__main__":
  import sys

  prompt = " ".join(sys.argv[1:]) or "Hello"
  result = generate(prompt)
  if hasattr(result, "__iter__") and not isinstance(result, str):
    for part in result:  # pragma: no cover - manual CLI run
      print(part, end="")
  else:
    print(result)
