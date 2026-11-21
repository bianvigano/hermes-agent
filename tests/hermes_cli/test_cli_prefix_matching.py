"""Tests for slash command prefix matching in HermesCLI.process_command."""
from unittest.mock import MagicMock, patch
from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = None
    cli_obj._pending_input = MagicMock()
    return cli_obj


class TestSlashCommandPrefixMatching:
    def test_unique_prefix_dispatches_command(self):
        """/con should dispatch to /config when it uniquely matches."""
        cli_obj = _make_cli()
        with patch.object(cli_obj, 'show_config') as mock_config:
            cli_obj.process_command("/con")
        mock_config.assert_called_once()






    def test_skill_command_prefix_matches(self):
        """A prefix that uniquely matches a skill command should dispatch it."""
        cli_obj = _make_cli()
        fake_skill = {"/test-skill-xyz": {"name": "Test Skill", "description": "test"}}
        printed = []
        cli_obj.console.print = lambda *a, **kw: printed.append(str(a))

        import cli as cli_mod
        with patch.object(cli_mod, '_skill_commands', fake_skill):
            cli_obj.process_command("/test-skill-xy")

        # Should NOT show "Unknown command" — should have dispatched or attempted skill
        unknown = any("Unknown command" in p for p in printed)
        assert not unknown, f"Expected skill prefix to match, got: {printed}"


    def test_shortest_match_preferred_over_longer_skill(self):
        """/qui should dispatch to /quit (5 chars) not report ambiguous with /quint-pipeline (15 chars)."""
        cli_obj = _make_cli()
        fake_skill = {"/quint-pipeline": {"name": "Quint Pipeline", "description": "test"}}

        import cli as cli_mod
        with patch.object(cli_mod, '_skill_commands', fake_skill):
            # /quit is caught by the exact "/quit" branch → process_command returns False
            result = cli_obj.process_command("/qui")

        # Returns False because /quit was dispatched (exits chat loop)
        assert result is False
        printed = " ".join(str(c) for c in cli_obj.console.print.call_args_list)
        assert "Ambiguous" not in printed

    def test_tied_shortest_matches_still_ambiguous(self):
        """/re matches /reset and /retry (both 6 chars) — no unique shortest, stays ambiguous."""
        cli_obj = _make_cli()
        printed = []
        import cli as cli_mod
        with patch.object(cli_mod, '_cprint', side_effect=lambda t: printed.append(t)):
            cli_obj.process_command("/re")
        combined = " ".join(printed)
        assert "Ambiguous" in combined or "Did you mean" in combined

    def test_exact_typed_name_dispatches_over_longer_match(self):
        """/help typed with /help-extra skill installed → exact match wins."""
        cli_obj = _make_cli()
        fake_skill = {"/help-extra": {"name": "Help Extra", "description": ""}}
        import cli as cli_mod
        with patch.object(cli_mod, '_skill_commands', fake_skill), \
             patch.object(cli_obj, 'show_help') as mock_help:
            cli_obj.process_command("/help")
        mock_help.assert_called_once()
        printed = " ".join(str(c) for c in cli_obj.console.print.call_args_list)
        assert "Ambiguous" not in printed

    def test_mcp_preserves_quoted_case_sensitive_arguments(self):
        cli_obj = _make_cli()
        with patch("hermes_cli.mcp_config.mcp_command") as handler:
            assert cli_obj.process_command('/mcp add "My Server" --url https://example.test/MCP')
        args = handler.call_args.args[0]
        assert args.name == "My Server"
        assert args.url == "https://example.test/MCP"
        assert args.mcp_action == "add"

    def test_mcp_exit_and_invalid_input_allow_next_command(self):
        cli_obj = _make_cli()
        with patch("hermes_cli.mcp_config.mcp_command", side_effect=SystemExit(2)):
            assert cli_obj.process_command("/mcp list")
        with patch("hermes_cli.mcp_config.mcp_command") as handler:
            assert cli_obj.process_command("/mcp add")
            assert cli_obj.process_command('/mcp add "unterminated')
            handler.assert_not_called()
            assert cli_obj.process_command("/mcp list")
        assert handler.call_args.args[0].mcp_action == "list"

    def test_mcp_preserves_ansi_output_while_prompt_toolkit_is_active(self):
        import asyncio
        import io
        from types import SimpleNamespace

        cli_obj = _make_cli()
        app = MagicMock(is_running=True)
        cli_obj._app = app
        terminal = io.StringIO()
        proxy = SimpleNamespace(original_stdout=terminal)

        async def fake_run_in_terminal(func, **_kwargs):
            func()

        app.create_background_task.side_effect = asyncio.run
        with patch("hermes_cli.mcp_config.mcp_command",
                   side_effect=lambda _args: print("\x1b[36mMCP Servers:\x1b[0m")), \
             patch("sys.stdout", proxy), patch("sys.stderr", proxy), \
             patch("prompt_toolkit.application.run_in_terminal", fake_run_in_terminal):
            cli_obj._handle_mcp_command("/mcp list")
        assert terminal.getvalue() == "\x1b[36mMCP Servers:\x1b[0m\n"
