# 006 ETH AI AlphaEvolve 生产部署与 OKX 对接指引

## 一、 TradingView V6 策略挂载
1. 打开 TradingView，进入以太坊合约图表： (Binance) 或  (OKX)。
2. 将 K 线时间周期切换为 **15 分钟 (15m)**。
3. 打开底部的 **Pine Editor**，新建脚本并将  源码完整粘贴。
4. 点击 **Add to chart (添加到图表)**，在属性面板中设置初始资金 10,000 USDT，单笔委托基准为 50%。

## 二、 OKX 信号交易 (Signal Trading) Webhook 对接
1. 登录 OKX 网页端，进入 **交易 -> 策略交易 -> 信号策略 -> 创建信号**。
2. 填写信号名称（如 ），获取专属的 **Webhook URL** 与 **信号 Token**。
3. 在 TradingView 图表右上角点击 **Alert (创建警报)**：
   - **Condition**: 选择 。
   - **Action**: 勾选 **Webhook URL**，粘贴 OKX 的 Webhook 地址。
   - **Message**: 配置标准化 JSON 动作载荷：
     

## 三、 实盘风控设置
- **保证金模式**: 必须强制选择 **逐仓模式 (Isolated Margin)**，杠杆建议控制在 2x ~ 3x。
- **单笔本金保护**: 账户总资金仅划转计划跟单金额，避免全仓联动风险。
