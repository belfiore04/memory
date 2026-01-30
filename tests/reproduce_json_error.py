import json
import logging
import re

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_parsing_dirty_json():
    # 模拟更极端的畸形数据：Key 本身包含了换行符和引号
    # 这种情况类似于: { "\n \"should_intervene\"": true }
    dirty_json_text = r"""
    {
        "\n \"should_intervene\"": true,
        "suggestion": "Test suggestion"
    }
    """
    
    print(f"原始数据:\n{dirty_json_text}")
    
    try:
        # 1. 尝试 json.loads (Python 标准库通常能处理空白，看看到底哪里出了问题)
        result = json.loads(dirty_json_text)
        print(f"解析结果 Keys: {[k for k in result.keys()]}") # 看看 Key 到底长什么样
        
        # 2. 模拟当前的业务逻辑
        should_intervene = False
        suggestion = None
        
        # 模拟当前代码的逻辑
        # Note: 标准 json.loads 会自动 strip key 吗？不会。
        # 如果 Key 本身包含换行符（在引号内），那就是真的包含。
        # 但如果是: \n "key"，这个 \n 在引号外，是合法的 JSON 空白。
        # 除非 LLM 返回的是: { "\n key": ... } -> Key 内部包含换行
        
        # 让我们构造一个 Key 内部包含换行的恶心情况，这才是 KeyError 的元凶
        # 错误信息是: KeyError: '\n "should_intervene"'
        # 这看起来像是有人试图用 result['\n "should_intervene"'] 去访问？
        # 或者解析出来的 Key 就是 '\n "should_intervene"'？这不可能，除非引号没对齐。
        
        # 等等，如果代码里写的是 result["should_intervene"] 报错 KeyError
        # 说明 key 不叫 "should_intervene"。
        # 错误信息显示 KeyError: '\n "should_intervene"'
        # 这意味着在 dict 里根本没找到这个 key。
        # 让我模拟解析后的字典看看。
        
        found = False
        for key, value in result.items():
            # [FIXED LOGIC]
            clean_key = key.strip().strip('"').strip("'").strip()
            print(f"Checking key: '{key}' -> Clean: '{clean_key}'")
            if clean_key == "should_intervene":
                should_intervene = value
                found = True
        
        if not found:
            print("❌ 未找到 should_intervene 字段")
        else:
            print("✅ 成功找到字段")
            
    except Exception as e:
        print(f"❌ 解析异常: {e}")

if __name__ == "__main__":
    test_parsing_dirty_json()
