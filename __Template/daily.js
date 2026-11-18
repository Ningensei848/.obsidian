function getDate(tp) {
    const { dailyNoteDir, dailyNoteFormat } = tp.user.config(tp);
    const path = tp.config.target_file.path;
    const prefix = dailyNoteDir ? `${dailyNoteDir}/` : "";
    const relative = path.startsWith(prefix) ? path.slice(prefix.length).replace(/\.md$/, "") : "";
    // 今日ではなく対象ファイルの日付を使う。過去日・未来日の作成にも対応する。
    const date = tp.obsidian.moment(relative, dailyNoteFormat, true);
    if (!relative || !date.isValid()) {
        tp.user.util().fail("DAILY_DATE_INVALID", "daily-date");
    }
    return date;
}

async function findPrevNote(tp, isEmbed = false) {
    const { dailyNoteDir, dailyNoteFormat, maxLookback } = tp.user.config(tp);
    const anchor = getDate(tp);
    for (let days = 1; days <= maxLookback; days += 1) {
        const date = anchor.clone().subtract(days, "days");
        const linkPath = [dailyNoteDir, date.format(dailyNoteFormat)].filter(Boolean).join("/");
        let file;
        try {
            file = tp.app.vault.getAbstractFileByPath(`${linkPath}.md`);
        } catch (error) {
            tp.user.util().fail("DAILY_LOOKUP_FAILED", "previous-note-lookup", error);
        }
        if (!file || file.extension !== "md") continue;
        const label = date.format("YYYY-MM-DD");
        if (isEmbed) {
            const heading = typeof isEmbed === "string" ? `#${isEmbed}` : "";
            return `![[${linkPath}${heading}|${label}]]`;
        }
        return `[[${linkPath}|${label}]]`;
    }
    return "前回のノートなし";
}

module.exports = { getDate, findPrevNote };
