# LOL TCG 卡牌验证流程

## 验证方式

直接使用 `web_search` + `read_web_page`，无需图片验证。

## 验证流程

### Step 1: 搜索卡牌

``` txt
site:riftbound.wiki.fextralife.com {卡牌名}
```

或使用卡牌编号搜索：

``` txt
site:riftbound.wiki.fextralife.com {卡牌编号}
```

### Step 2: 读取详情页

URL 格式：

``` txt
https://riftbound.wiki.fextralife.com/{卡牌编号}+{卡牌名URL编码}
```

示例：

``` txt
https://riftbound.wiki.fextralife.com/OGS-023+Garen+Might+of+Demacia
```

### Step 3: 提取卡牌数据

返回数据示例：

``` txt
Name: Garen Might of Demacia
Set: Origins - Proving Grounds
Rarity: Rare
Card Number: OGS-023
Type: Legend
Domain: Body, Order
Effect: When you conquer, if you have 4+ units at that battlefield, draw 2.
```

## 数据源

- **主站**: riftbound.wiki.fextralife.com
- **注意**: 需要知道卡牌编号或先用 `web_search` 搜索
