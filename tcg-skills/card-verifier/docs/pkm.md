# PKM 卡牌验证流程

## 数据源优先级

1. **Limitless TCG** (`limitlesstcg.com`) - 首选，能正确标记能量属性 `[C]`
2. **52poke 百科** (`wiki.52poke.com`) - 备选，能正确标记能量属性
3. **pokemon-card.com + 图片 OCR** - 兜底，仅当上述来源无法确认时使用

## 验证流程

### Step 1: 直接访问 Limitless TCG

使用 `read_web_page` 直接访问卡牌页面：

``` txt
https://limitlesstcg.com/cards/ja/{SET_ID}/{CARD_NUMBER}
```

示例：`https://limitlesstcg.com/cards/ja/SV10/096`

Limitless 的文本格式示例：

- `おたがいの場の [ C ] ポケモン` → 無色宝可梦
- `[R] エネルギー` → 炎能量

如果页面存在且信息完整，验证完成。

### Step 2: 直接访问 52poke 百科

如果 Limitless 返回 404 或信息不完整，使用 `read_web_page` 直接访问：

``` txt
https://wiki.52poke.com/wiki/{卡牌中文名}（TCG）
```

示例：`https://wiki.52poke.com/wiki/火箭隊的監視塔（TCG）`

52poke 会用图标或文字标记能量属性（如 `[無色]`、`[超]`）。

如果页面存在且信息完整，验证完成。

### Step 3: 兜底 - 标记为无法验证

如果 Limitless 和 52poke 都找不到该卡牌：

1. 在 changelog 中标记为 `[UNVERIFIED]`
2. 记录原因（如"M3 新卡，数据库未收录"）
3. **不做修正**，保留原文

#### pokemon-card.com 不可用作数据源

> - 搜索页是 JavaScript 渲染，read_web_page 无法获取结果
> - 详情页文本丢失能量符号（图标无法被解析）
> - 即使下载图片用 OCR，准确率也不够可靠

## 能量符号对照表

| 符号 | Limitless | 属性 | 日文 |
|------|-----------|------|------|
| ★ | [C] | 無色 | むしょく |
| [草] | [G] | 草 | くさ |
| [火] | [R] | 炎 | ほのお |
| [水] | [W] | 水 | みず |
| [雷] | [L] | 雷 | かみなり |
| [超] | [P] | 超 | ちょう |
| [斗] | [F] | 闘 | とう |
| [悪] | [D] | 悪 | あく |
| [鋼] | [M] | 鋼 | はがね |
| [龍] | [N] | 龍 | ドラゴン |

## 数据源

- **Limitless TCG**: limitlesstcg.com（社区维护，解析完善）
- **52poke 百科**: wiki.52poke.com（中文百科）
- **pokemon-card.com**: 公式（图片验证用）
