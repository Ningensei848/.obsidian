<%*
const noteTitle = await tp.user.util().prepareMisc(tp);
-%>
---
title: <% JSON.stringify(noteTitle) %>
date: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - Misc
aliases:
  - <% JSON.stringify(tp.date.now("YYYY年MM月DD日")) %>
---

# <% noteTitle %>

## これは何？

<!-- 簡単な説明。まだ分からなければ「未定義」と書く -->

## どこで使う？

<!-- 現場での利用場面や関連業務 -->

## 関連キーワード

%%
- [[関連語1]]
- [[関連語2]]
%%

---

### メモ

-
