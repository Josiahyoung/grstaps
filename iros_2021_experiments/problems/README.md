# IROS 最小运行算例

这两个自建算例用于检查代码流程，不是论文原始实验数据。输入结构、数组长度、索引范围和单机能力可行性已检查；尚未在实际 C++ 程序中运行。

## 文件与位置

两个算例分别放在 0/config.json 和 1/config.json，共用 ../../maps/test.json。
从 iros_2021_experiments 目录运行，程序会在对应算例目录写入 itags_output.json。

streets 和 buildings 为空数组，仍须保留。三个固定位置按初始化顺序编号：
- 0: hospital，(0, 0)
- 1: fire_station，(0.5, 0)
- 2: construction_company，(1, 0)

这些名称是现有解析器要求的字段；本例仅将其用作位置标签。输入位置保持原始坐标，不乘一百万。这是对空中矩形规划区域的测试，不测试地面道路可达性。

## 特征列

robot_traits 每行依次为：
[巡检能力, 喷施能力, 速度, 预留能力, 规划器编号]

speed_index 为 2，mp_index 为 4。所有机器人速度为 1 原始距离单位/时间单位，规划器编号为 1（空中）。
预留列为 0。任务需求中速度与规划器列填 0，避免将软件选择标记误作作业需求。
能力数值只为构造软件测试，不代表真实无人机参数。

## 算例 0

一台机器人执行 inspect_move，位置 0 -> 1，基础时长为 2。
起始位置即任务起点，无额外转场。直线距离 0.5、速度 1，理想总工期为 2.5。
实际路径由采样规划器生成，可能更长或在时间限制内失败，因此不要求结果精确等于 2.5。

## 算例 1

robot 0 仅具备巡检能力，从位置 0 开始；robot 1 仅具备喷施能力，从位置 1 开始。
task 0 为巡检移动 0 -> 1，基础时长为 2；task 1 为喷施移动 1 -> 2，基础时长为 3。
ordering_constraints = [[0, 1]] 表示 task 0 完成后才能执行 task 1。
应验证 task 0 由 robot 0 执行，task 1 由 robot 1 执行；任务 1 的开始时间不早于任务 0 的结束时间。
两段直线长度均为 0.5，理想总工期为 6；它是人工计算的参考值，不是已经测得的结果。
本例按能力确定分工，不用于评价优化器在多个可行分配间的选择质量。

## 运行

先确认已拉取尺度修复提交并编译成功，再从仓库根目录执行：

```bash
cd ~/projects/grstaps/iros_2021_experiments
../build/iros_2021_experiments/experiments -p 0 -m test.json
```

检查算例 0 成功后运行算例 1：

```bash
../build/iros_2021_experiments/experiments -p 1 -m test.json
```

查看结果：

```bash
cat problems/0/itags_output.json
cat problems/1/itags_output.json
```

检查 solved、makespan、solution.allocation、solution.schedule、solution.motion_plans。
确认起终点、能力分工、先后关系和路径范围，而不只检查程序退出状态。
同一编号重复运行会覆盖该目录的 itags_output.json；比较实验前请另存结果。
