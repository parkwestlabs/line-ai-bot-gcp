from textwrap import dedent

from utils.llm_utils import clean_llm_output


class TestCleanLlmOutput:
    """clean_llm_output 関数のテスト"""

    def test_basic_bold_removal(self):
        """基本的な太字（**）が除去されること"""
        input_text = "This is **bold** text."
        expected = "This is bold text."

        assert clean_llm_output(input_text) == expected

    def test_multiple_bold_in_one_line(self):
        """1行に複数の太字がある場合、すべて除去されること"""
        input_text = "Here is **first** and **second** bold."
        expected = "Here is first and second bold."

        assert clean_llm_output(input_text) == expected

    def test_bold_with_asterisk_inside(self):
        """太字の中に単一のアスタリスク（掛け算記号など）が含まれていても正しく処理されること"""
        input_text = "Formula: **a * b** is multiplication."
        expected = "Formula: a * b is multiplication."

        assert clean_llm_output(input_text) == expected

    def test_list_normalization(self):
        """箇条書きのリストが整形されつつ太字が除去されること (mdformatの作用確認)"""
        # リスト記号を同一（-）にして、1つの連続したリストとして認識させます
        input_text = dedent("""\
            - **Item 1**
            - Item 2
            - **Item 3**""")
        expected = dedent("""\
            - Item 1
            - Item 2
            - Item 3""")

        assert clean_llm_output(input_text) == expected

    def test_gfm_table_formatting_and_unbolding(self):
        """GFMテーブルの太字が解除され、かつ列幅が正しく揃うこと"""
        input_text = dedent("""\
            | **Header 1** | Header 2 |
            | --- | --- |
            | **Value A** | Value B |""")

        # フォーマット後：太字解除後の文字数に合わせてテーブル幅がハイフンで調整される
        expected = dedent("""\
            | Header 1 | Header 2 |
            | -------- | -------- |
            | Value A  | Value B  |""")

        assert clean_llm_output(input_text) == expected

    def test_italic_is_preserved(self):
        """一重のアスタリスク（*斜体*）は除去されずに保持されること"""
        input_text = "This is *italic* and **bold**."
        expected = "This is *italic* and bold."

        assert clean_llm_output(input_text) == expected

    def test_no_bold_text(self):
        """太字が含まれないテキストを入力した場合、変更（整形のみ）で正常終了すること"""
        input_text = "Plain text with no formatting."
        expected = "Plain text with no formatting."

        assert clean_llm_output(input_text) == expected
