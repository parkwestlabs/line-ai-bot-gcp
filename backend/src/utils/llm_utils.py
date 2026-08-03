import re

import mdformat


def clean_llm_output(text: str) -> str:
    # 1. 太字のアスタリスクを除去
    no_bold = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    # 2. リストやテーブルを含めて綺麗なMarkdownに整形
    formatted_text = mdformat.text(no_bold, extensions=["gfm"])

    # 3. チャットUI用に末尾の改行を除去する
    return formatted_text.rstrip("\n")
