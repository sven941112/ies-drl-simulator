# 综合能源数学模型与代码对应

## 1. 模型边界

研究对象为并网园区单母线电—热—冷—气能源枢纽。一个调度周期含 $T=24$ 个时段，$\Delta t=1\,\mathrm{h}$。功率单位 kW，能量单位 kWh，费用单位 CNY，排放单位 kgCO2。不同能源的 kW 表示对应载能形式的能流率。

本版本忽略电、热、气网络内部输送约束；天然气供应仅按能量和价格结算，没有气网压力模型。所有效率和性能系数为常数。热量过剩允许经显式散热通道排放；实际园区若无该能力，应取消该假设并加入对应约束。

| 缩写 | 英文全称 | 中文 |
|---|---|---|
| IES | Integrated Energy System | 综合能源系统 |
| CHP | Combined Heat and Power | 热电联产 |
| HP | Heat Pump | 热泵 |
| GB | Gas Boiler | 燃气锅炉 |
| AC | Absorption Chiller | 吸收式制冷机 |
| EC | Electric Chiller | 电制冷机 |
| BESS | Battery Energy Storage System | 电池储能系统 |
| TES | Thermal Energy Storage | 蓄热系统 |
| SOC | State of Charge | 荷电状态 / 储能相对能量状态 |
| COP | Coefficient of Performance | 性能系数 |

## 2. 多能转换设备

设 $F_t^{chp}$ 为 CHP 燃气输入的能流率：

$$P_t^{chp}=\eta_e F_t^{chp},\qquad Q_t^{chp}=\eta_h F_t^{chp}.$$

$$0\le F_t^{chp}\le \overline F^{chp},\qquad |F_t^{chp}-F_{t-1}^{chp}|\le R^{chp}\Delta t.$$

其中 $P$ 为电功率，$Q$ 为热功率；$\eta_e,\eta_h$ 为发电和供热效率。第一时段取 $F_{-1}^{chp}=0$。本版本不包含最小开机出力、启停成本和最小启停时间，不可直接用于机组组合问题。

燃气锅炉、热泵与制冷设备：

$$Q_t^{gb}=\eta_{gb}F_t^{gb},\quad Q_t^{hp}=COP_{hp}P_t^{hp},$$
$$C_t^{ac}=COP_{ac}Q_t^{ac},\quad C_t^{ec}=COP_{ec}P_t^{ec}.$$

$F^{gb}$ 为锅炉燃气输入；$P^{hp}$ 为热泵耗电；$Q^{ac}$ 为吸收式制冷耗热；$P^{ec}$ 为电制冷耗电；$C$ 为供冷功率。各设备均有配置文件给定的额定上限。

这里的燃气输入单位是 kW_gas，采用与燃气价格一致的热值口径，不是 m³/h。接入体积流量时应先按现场采用的低位或高位热值转换，并统一效率口径。示例燃气价格也不是实时市场价格。

## 3. 电池与蓄热

对储能 $j\in\{b,th\}$，定义母线侧带符号功率 $u_t^j$：**正值放能、负值充能**。

$$E_{t+1}^{j}=E_t^{j}+\left(\eta_c^{j}[-u_t^{j}]_+-\frac{[u_t^{j}]_+}{\eta_d^{j}}\right)\Delta t,$$

$$E_{min}^{j}\le E_t^{j}\le E_{max}^{j},\qquad SOC_t^{j}=E_t^{j}/\overline E^{j}.$$

$[x]_+=\max(x,0)$；$E$ 为储能量，$\overline E$ 为容量，$\eta_c,\eta_d$ 为充放效率。单个带符号功率保证同一时段不同时充放能。此处未考虑自放电、温度相关损耗或电池寿命状态演化。

每步执行功率根据当前能量限制为：

$$-\min\left(\overline u^j,\frac{E_{max}^j-E_t^j}{\eta_c^j\Delta t}\right)
\le u_t^j\le
\min\left(\overline u^j,\frac{(E_t^j-E_{min}^j)\eta_d^j}{\Delta t}\right).$$

`storage_dispatch()` 在更新能量之前修正功率，不通过事后强行截断 SOC 掩盖能量不守恒。储能建模可对照 [PyPSA 储能文档](https://docs.pypsa.org/latest/user-guide/optimization/storage/)；本项目采用上述更简化的无自放电模型。

## 4. 能量平衡与不可行状态

令 $L_t^e,L_t^h,L_t^c$ 为电、热、冷负荷；$P_t^{re}=P_t^{pv}+P_t^{wind}$ 为可用新能源出力；$P_t^{curt}$ 为弃风弃光。

电平衡：

$$P_t^{re}-P_t^{curt}+P_t^{chp}+u_t^b+P_t^{buy}+s_t^e
=L_t^e+P_t^{hp}+P_t^{ec}+P_t^{sell}+d_t^e.$$

热平衡：

$$Q_t^{chp}+Q_t^{hp}+Q_t^{gb}+u_t^{th}+s_t^h
=L_t^h+Q_t^{ac}+Q_t^{dump}.$$

冷平衡：

$$C_t^{ac}+C_t^{ec}+s_t^c=L_t^c.$$

其中 $P^{buy},P^{sell}$ 为电网购售电；$Q^{dump}$ 为散热。$s^e,s^h,s^c\ge0$ 是虚拟供能缺口；$d^e\ge0$ 为新能源已全部可弃后仍无法处置的电力过剩。

**四个虚拟量中任一个超过容差，该时段即不可行。** 它们用于避免训练时程序中断、诊断动作问题，并不是系统安装了无限备用电源、热源或电阻负载。

尤其是 $s^e>0$ 时，部分电力需求未能满足，按计划计算出的热泵 / 电制冷产出不能被视作已经物理实现。此时整条当期计划均标为不可行，不能报告为“电热冷负荷全部满足”。

`electric_residual_kw` 等残差包含虚拟量，只用于检查计算账目守恒；残差接近零不等于实际可行，必须同时检查 `infeasible` 和各缺口。

## 5. 自动补足的执行顺序

1. 将动作映射到 CHP、HP、BESS、TES、AC 的物理设定值。
2. 修正 CHP 爬坡、电池和蓄热功率边界。
3. 将 AC 的耗热限制到不超过当前冷需求对应的耗热；EC 补足其余冷需求。
4. 根据 CHP、HP、TES 与 AC 计算热缺口；GB 在容量内补足，富余热量进入散热。
5. 根据电负荷、HP、EC、新能源、CHP、BESS 计算净购电需求；电网在容量内平衡。
6. 超过送出能力的富余电先弃新能源；仍有过剩则记录 $d^e$。无法满足的需求记录对应 $s$。
7. 更新能量与历史状态，计算费用、奖励和诊断信息。

燃气锅炉、电制冷机和电网是确定性补足设备，因此不是独立动作。该规则减少动作维度，同时限制了智能体可选择的补足方式；后续比较优化求解器时必须说明这一差别。

## 6. 费用与奖励

$$C_t^{op}=\Delta t\left(c_t^{buy}P_t^{buy}-c_t^{sell}P_t^{sell}
+c^{gas}(F_t^{chp}+F_t^{gb})+c_b^{wear}|u_t^b|+c_{th}^{wear}|u_t^{th}|\right)+c^{CO2}M_t,$$

$$M_t=\Delta t\left(\mu^{grid}P_t^{buy}+\mu^{gas}(F_t^{chp}+F_t^{gb})\right).$$

$c$ 为相应单位价格或成本，$\mu$ 为排放因子。只对购入电力和消耗天然气计入排放；售电不获得避免排放抵扣。$c^{CO2}M_t$ 是示例内部碳成本，不是已经实现了碳市场交易机制。

$$C_t^{pen}=\Delta t\left[\lambda_s(s_t^e+s_t^h+s_t^c+d_t^e)
+\lambda_{curt}P_t^{curt}+\lambda_{dump}Q_t^{dump}\right].$$

$$C_T^{terminal}=\lambda_T\left(|E_T^b-E_0^b|+|E_T^{th}-E_0^{th}|\right).$$

$$\min_\pi\;\mathbb E_\pi\left[\sum_{t=0}^{T-1}(C_t^{op}+C_t^{pen})+C_T^{terminal}\right],$$

$$r_t=-\frac{C_t^{op}+C_t^{pen}+\mathbb 1_{t=T-1}C_T^{terminal}}{S}.$$

$\pi$ 为策略，$S=1000$ 为固定奖励尺度。训练使用 $\gamma=1$ 对应有限日周期内不折扣的费用，SAC 还具有其算法本身的熵正则项。

期末能量恢复是**软目标**，并未严格保证 $E_T=E_0$。费用比较必须同时报告期末偏差；加入 MILP 后，应统一期末条件再比较。`operating_cost_cny` 与包含惩罚的 `objective_cny` 分开输出。

## 7. 默认参数示例

| 参数 | 默认值 |
|---|---:|
| CHP 最大燃气输入 / 发电效率 / 供热效率 | 350 kW_gas / 0.35 / 0.45 |
| CHP 燃气输入变化率 | 150 kW_gas/h |
| 锅炉最大供热 / 效率 | 500 kW_th / 0.90 |
| 热泵最大耗电 / COP | 180 kW_e / 3.0 |
| AC 最大耗热 / COP | 180 kW_th / 0.7 |
| EC 最大供冷 / COP | 600 kW_c / 4.0 |
| 电池容量 / 功率 | 500 kWh_e / 120 kW_e |
| 蓄热容量 / 功率 | 600 kWh_th / 160 kW_th |
| 电池、蓄热充放效率 | 各 0.95 |
| SOC 范围 / 初始值 | 0.10–0.90 / 0.50 |
| 电网最大购电 / 售电 | 1000 kW / 200 kW |
| 供能缺口惩罚 / 期末能量偏差惩罚 | 100 CNY/kWh / 2 CNY/kWh |

这些参数只用于软件演示。正式开发应使用设备资料及现场数据重新校准，完整参数以 `configs/default.json` 为准。
