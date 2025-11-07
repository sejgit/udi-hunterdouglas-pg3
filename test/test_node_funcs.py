"""Tests for the node_funcs utility module.

(C) 2025 Stephen Jenkins
"""

from utils.node_funcs import get_valid_node_address, get_valid_node_name


class TestGetValidNodeAddress:
    """Tests for get_valid_node_address function."""

    def test_simple_name_lowercase(self):
        """Test that simple name is converted to lowercase."""
        result = get_valid_node_address("MyNode")
        assert result == "mynode"

    def test_removes_special_characters(self):
        """Test that special characters are removed."""
        special_chars = "<>`~!@#$%^&*(){}[]?/\\;:\"'"
        result = get_valid_node_address(f"Node{special_chars}Name")
        assert result == "nodename"

    def test_preserves_valid_characters_when_short(self):
        """Test that valid characters are preserved when name is short."""
        result = get_valid_node_address("Node123")
        assert result == "node123"
        assert len(result) <= 14

    def test_truncates_to_max_length(self):
        """Test that long names are truncated to max_length (default 14)."""
        long_name = "ThisIsAVeryLongNodeName"  # 23 characters
        result = get_valid_node_address(long_name)
        assert len(result) == 14
        # Should be lowercase and end with "nodename"
        assert result.endswith("nodename")

    def test_custom_max_length(self):
        """Test with custom max_length parameter."""
        result = get_valid_node_address("VeryLongName", max_length=8)
        assert len(result) == 8
        assert result == "longname"

    def test_short_name_not_padded(self):
        """Test that short names are not padded."""
        result = get_valid_node_address("abc")
        assert result == "abc"

    def test_empty_string(self):
        """Test with empty string."""
        result = get_valid_node_address("")
        assert result == ""

    def test_only_special_characters(self):
        """Test with only special characters."""
        result = get_valid_node_address("!@#$%^&*()")
        assert result == ""

    def test_utf8_characters_preserved(self):
        """Test that UTF-8 characters are preserved."""
        result = get_valid_node_address("Café123")
        assert result == "café123"

    def test_whitespace_preserved(self):
        """Test that whitespace is preserved."""
        result = get_valid_node_address("Node Name Test")
        assert result == "node name test"

    def test_multiple_spaces_preserved(self):
        """Test that multiple spaces are preserved."""
        result = get_valid_node_address("Node  Name")
        assert result == "node  name"

    def test_tabs_preserved(self):
        """Test that tabs are preserved."""
        result = get_valid_node_address("Node\tName")
        assert result == "node\tname"

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        result = get_valid_node_address("Node123")
        assert result == "node123"

    def test_hyphen_and_underscore_preserved(self):
        """Test that hyphens and underscores are preserved."""
        result = get_valid_node_address("Node-Test_Name")
        assert result == "node-test_name"

    def test_mixed_case_to_lowercase(self):
        """Test that mixed case is converted to lowercase."""
        result = get_valid_node_address("MiXeD")  # 5 chars, under limit
        assert result == "mixed"
        assert result.islower()

    def test_truncation_from_end(self):
        """Test that truncation takes from the end of the string."""
        result = get_valid_node_address("BeginningMiddleEnd", max_length=10)
        assert result == "gmiddleend"

    def test_exact_max_length(self):
        """Test name exactly at max_length."""
        result = get_valid_node_address("ExactlyLength!", max_length=13)
        assert result == "exactlylength"
        assert len(result) == 13


class TestGetValidNodeName:
    """Tests for get_valid_node_name function."""

    def test_simple_name_case_preserved(self):
        """Test that simple name preserves case."""
        result = get_valid_node_name("MyNode")
        assert result == "MyNode"

    def test_removes_special_characters(self):
        """Test that special characters are removed."""
        special_chars = "<>`~!@#$%^&*(){}[]?/\\;:\"'"
        result = get_valid_node_name(f"Node{special_chars}Name")
        assert result == "NodeName"

    def test_preserves_case(self):
        """Test that case is preserved (unlike get_valid_node_address)."""
        result = get_valid_node_name("MiXeD-CaSe_NaMe")
        assert result == "MiXeD-CaSe_NaMe"

    def test_truncates_to_max_length(self):
        """Test that long names are truncated to max_length (default 32)."""
        long_name = "ThisIsAVeryLongNodeNameThatExceedsMaximumLength"  # 48 chars
        result = get_valid_node_name(long_name)
        assert len(result) == 32
        # Should end with "MaximumLength"
        assert result.endswith("MaximumLength")

    def test_custom_max_length(self):
        """Test with custom max_length parameter."""
        result = get_valid_node_name("VeryLongNodeName", max_length=10)  # 16 chars
        assert len(result) == 10
        # Should end with "NodeName" or "odeName"
        assert "Name" in result

    def test_short_name_not_padded(self):
        """Test that short names are not padded."""
        result = get_valid_node_name("Short")
        assert result == "Short"

    def test_empty_string(self):
        """Test with empty string."""
        result = get_valid_node_name("")
        assert result == ""

    def test_only_special_characters(self):
        """Test with only special characters."""
        result = get_valid_node_name("!@#$%^&*()")
        assert result == ""

    def test_utf8_characters_preserved(self):
        """Test that UTF-8 characters are preserved."""
        result = get_valid_node_name("Café Test")
        assert result == "Café Test"

    def test_whitespace_preserved(self):
        """Test that whitespace is preserved."""
        result = get_valid_node_name("Node Name Test")
        assert result == "Node Name Test"

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        result = get_valid_node_name("Node123")
        assert result == "Node123"

    def test_hyphen_and_underscore_preserved(self):
        """Test that hyphens and underscores are preserved."""
        result = get_valid_node_name("Node-Test_Name")
        assert result == "Node-Test_Name"

    def test_truncation_from_end(self):
        """Test that truncation takes from the end of the string."""
        result = get_valid_node_name("BeginningMiddleEnd", max_length=10)
        assert result == "gMiddleEnd"

    def test_exact_max_length(self):
        """Test name exactly at max_length."""
        result = get_valid_node_name("ExactlyThisLength!", max_length=17)
        assert result == "ExactlyThisLength"
        assert len(result) == 17

    def test_default_max_32_characters(self):
        """Test default max_length is 32."""
        name_33_chars = "A" * 33
        result = get_valid_node_name(name_33_chars)
        assert len(result) == 32


class TestNodeFuncsComparison:
    """Tests comparing behavior of both functions."""

    def test_address_lowercase_name_preserves_case(self):
        """Test that address lowercases but name preserves case."""
        test_name = "MixedCaseName"

        address = get_valid_node_address(test_name)
        name = get_valid_node_name(test_name)

        assert address == "mixedcasename"
        assert name == "MixedCaseName"

    def test_different_default_max_lengths(self):
        """Test that default max lengths differ (14 vs 32)."""
        long_name = "A" * 50

        address = get_valid_node_address(long_name)
        name = get_valid_node_name(long_name)

        assert len(address) == 14
        assert len(name) == 32

    def test_both_remove_same_special_chars(self):
        """Test that both functions remove the same special characters."""
        test_string = "Test!@#Node"

        address = get_valid_node_address(test_string)
        name = get_valid_node_name(test_string)

        # Both should remove special chars
        assert "!" not in address
        assert "@" not in address
        assert "#" not in address
        assert "!" not in name
        assert "@" not in name
        assert "#" not in name

    def test_both_preserve_valid_chars(self):
        """Test that both preserve letters, numbers, spaces, hyphens, underscores."""
        test_string = "Node-123_Test Name"

        address = get_valid_node_address(test_string, max_length=50)
        name = get_valid_node_name(test_string, max_length=50)

        # Address should lowercase
        assert address == "node-123_test name"
        # Name should preserve case
        assert name == "Node-123_Test Name"


class TestNodeFuncsEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_consecutive_special_chars(self):
        """Test handling of consecutive special characters."""
        result_addr = get_valid_node_address("Node!!!Name")
        result_name = get_valid_node_name("Node!!!Name")

        assert result_addr == "nodename"
        assert result_name == "NodeName"

    def test_special_chars_at_start(self):
        """Test special characters at the start."""
        result_addr = get_valid_node_address("!!!StartNode")
        result_name = get_valid_node_name("!!!StartNode")

        assert result_addr == "startnode"
        assert result_name == "StartNode"

    def test_special_chars_at_end(self):
        """Test special characters at the end."""
        result_addr = get_valid_node_address("EndNode!!!")
        result_name = get_valid_node_name("EndNode!!!")

        assert result_addr == "endnode"
        assert result_name == "EndNode"

    def test_all_special_chars_in_pattern(self):
        """Test all special characters from the regex pattern."""
        special = "<>`~!@#$%^&*(){}[]?/\\;:\"'"
        result_addr = get_valid_node_address(f"A{special}B")
        result_name = get_valid_node_name(f"A{special}B")

        assert result_addr == "ab"
        assert result_name == "AB"

    def test_unicode_emoji_preserved(self):
        """Test that unicode emoji characters are preserved."""
        result_addr = get_valid_node_address("Node🎉Test")
        result_name = get_valid_node_name("Node🎉Test")

        # UTF-8 characters should be preserved
        assert "node" in result_addr
        assert "test" in result_addr
        assert "Node" in result_name
        assert "Test" in result_name

    def test_newline_preserved(self):
        """Test that newline characters are preserved."""
        result_addr = get_valid_node_address("Node\nName")
        result_name = get_valid_node_name("Node\nName")

        assert result_addr == "node\nname"
        assert result_name == "Node\nName"

    def test_period_preserved(self):
        """Test that periods are preserved (not in special chars list)."""
        result_addr = get_valid_node_address("Node.Name")
        result_name = get_valid_node_name("Node.Name")

        assert result_addr == "node.name"
        assert result_name == "Node.Name"

    def test_comma_preserved(self):
        """Test that commas are preserved (not in special chars list)."""
        result_addr = get_valid_node_address("Node,Name")
        result_name = get_valid_node_name("Node,Name")

        assert result_addr == "node,name"
        assert result_name == "Node,Name"
