/* Obsidian CLI の eval から実行する。端末側設定だけを変更する。 */
module.exports = async function enableTemplater(expectedVault) {
    const actual = app.vault.adapter.getBasePath?.();
    const normalize = (path) => {
        const value = path.replace(/\\/g, "/").replace(/\/+$/, "");
        return /^(?:[A-Za-z]:|\/\/)/.test(value) ? value.toLowerCase() : value;
    };
    if (typeof actual !== "string" || normalize(actual) !== normalize(expectedVault)) {
        throw new Error("DOT_OBSIDIAN_VAULT_MISMATCH");
    }
    if (app.vault.configDir !== ".obsidian") {
        throw new Error("DOT_OBSIDIAN_CONFIG_DIR_MISMATCH");
    }
    const plugin = app.plugins.plugins["templater-obsidian"];
    if (!plugin || typeof plugin.load_settings !== "function") {
        throw new Error("DOT_OBSIDIAN_TEMPLATER_NOT_LOADED");
    }
    await plugin.load_settings();
    const key = "templater-local-settings";
    const previous = app.loadLocalStorage(key) ?? {};
    app.saveLocalStorage(key, { ...previous, trigger_on_file_creation: true });
    if (app.loadLocalStorage(key)?.trigger_on_file_creation !== true) {
        throw new Error("DOT_OBSIDIAN_ACTIVATION_NOT_SAVED");
    }
    return "DOT_OBSIDIAN_TEMPLATER_ENABLED";
};
