from google import genai
from google.genai import types
from zConfig import get_config
PROXY_URL = get_config("proxy.http")
API_KEY =  get_config("ai.gemini.api_key")
MODEL= get_config("ai.gemini.model")

from google import genai
from google.genai import types


def call_gemini(
    prompt: str,
    api_key: str = API_KEY,
    proxy_url: str = PROXY_URL ,
    model: str = MODEL,
) -> str | None:
  """调用 Gemini 模型并返回生成文本的函数。

  :param prompt: 给模型的提示词/问题
  :param api_key: 你的 Google Gemini API Key
  :param proxy_url: 本地代理地址
  :param model: 模型名称
  :return: 模型回复的文本内容，如果出错则返回 None
  """
  # 1. 配置局部代理选项（不污染全局环境变量）
  http_options = types.HttpOptions(
      client_args={"proxy": proxy_url}, async_client_args={"proxy": proxy_url}
  )

  try:
    # 2. 初始化 Gemini 客户端
    client = genai.Client(api_key=api_key, http_options=http_options)

    print(f"正在使用模型 [{model}] 请求 Gemini...")

    # 3. 发送请求
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    return response.text

  except Exception as e:
    print(f"\n请求出错，请检查代理或 API Key 是否正确: {e}")
    return None