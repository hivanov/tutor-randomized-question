from tutor_randomized_question import plugin


def test_tutor_plugin_config_and_patches():
    # Verify tutor plugin module loaded properly
    assert hasattr(plugin, "hooks")

    # Verify defaults are registered
    config_defaults = [item[0] for item in plugin.hooks.Filters.CONFIG_DEFAULTS.apply([])]
    assert "RANDOMIZED_QUESTION_ENABLE" in config_defaults
    assert "RANDOMIZED_QUESTION_PIP_REQUIREMENT" in config_defaults

    # Verify environment patches are registered
    patch_targets = [item[0] for item in plugin.hooks.Filters.ENV_PATCHES.apply([])]
    assert "openedx-dockerfile-post-python-requirements" in patch_targets
    assert "openedx-lms-common-settings" in patch_targets
    assert "openedx-cms-common-settings" in patch_targets
