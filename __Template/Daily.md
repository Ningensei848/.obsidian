<%*
const noteDate = tp.user.daily.getDate(tp);
const previousNote = await tp.user.daily.findPrevNote(tp);
const previousAction = await tp.user.daily.findPrevNote(tp, "📌 Next Action");
-%>
---
title: <% JSON.stringify(`${noteDate.format("YYYY-MM-DD")} のデイリーノート`) %>
date: <% noteDate.format("YYYY-MM-DD") %>
tags:
  - daily
aliases:
  - <% JSON.stringify(noteDate.format("YYYY年MM月DD日")) %>
---

<% noteDate.format("YYYY年MM月DD日 (dddd)") %>

## 🔁 前回までのあらすじ

<% previousAction %>

## ✅ 今日の目標

### 午前

- [ ] …

### 午後

- [ ] …

## 📝 メモ

- …

## 🔗 関連リンク

- <% previousNote %>
- …

## 🤔 振り返り

- 良かったこと：
  - …
- 改善点：
  - …

## 📌 Next Action

- …
