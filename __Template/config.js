// Knewrova/__Template を基に、保存先を Daily notes の設定から取得する。
module.exports = (tp) => {
    const { getDailyOptions } = tp.user.util();
    const options = getDailyOptions(tp);
    return {
        dailyNoteDir: options.folder,
        dailyNoteFormat: options.format,
        maxLookback: 180,
    };
};
