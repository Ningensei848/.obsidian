function fail(code, stage, cause) {
    // 文書本文や例外メッセージは出さず、失敗の種類と実行箇所を残す。
    console.error("[dot-obsidian]", {
        code,
        stage,
        scope: "template",
        errorType: cause?.name ?? "TemplateError",
        attempts: 1,
        retry: "not_attempted",
    });
    throw new Error(`[${code}] ${stage}`);
}

function getUsername() {
    const env = typeof process === "undefined" ? {} : (process.env ?? {});
    const home = env.USERPROFILE || env.HOME || "";
    const leaf = home.replace(/[\\/]+$/, "").split(/[\\/]/).pop();
    const value = env.USERNAME || env.USER || env.LOGNAME || leaf || "user";
    // Windows のファイル名にも利用できる文字だけにする。
    return value.replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").replace(/[. ]+$/, "") || "user";
}

function getDailyOptions(tp) {
    const internal = tp.app.internalPlugins;
    const enabled = internal?.getEnabledPluginById?.("daily-notes");
    const options = enabled?.options ?? enabled?.instance?.options
        ?? internal?.plugins?.["daily-notes"]?.instance?.options;
    if (!options || typeof options.format !== "string" || !options.format) {
        fail("DAILY_SETTINGS_UNAVAILABLE", "daily-options");
    }
    return { folder: (options.folder ?? "").replace(/^\/+|\/+$/g, ""), format: options.format };
}

async function prepareMisc(tp) {
    let title = tp.file.title;
    if (!/^(untitled|無題のファイル|無題)(?:[ \d]*)$/i.test(title)) {
        return title;
    }
    const file = tp.config.target_file;
    const folder = file.parent?.path === "/" ? "" : (file.parent?.path ?? "");
    const base = `${tp.date.now("YYYYMMDD_HHmmss")}_${getUsername()}`;
    let suffix = 0;
    do {
        title = suffix ? `${base}_${suffix}` : base;
        suffix += 1;
    } while (tp.app.vault.getAbstractFileByPath([folder, `${title}.md`].filter(Boolean).join("/")));
    try {
        await tp.file.rename(title);
    } catch (error) {
        fail("MISC_RENAME_FAILED", "misc-rename", error);
    }
    return title;
}

module.exports = () => ({ getUsername, getDailyOptions, prepareMisc, fail });
