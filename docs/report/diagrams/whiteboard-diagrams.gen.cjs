const fs = require("fs");
const path = require("path");

const outDir = __dirname;

const C = {
  text: "#1F2329",
  sub: "#646A73",
  line: "#BBBFC4",
  blueBg: "#F0F4FC",
  blue: "#5178C6",
  purpleBg: "#EAE2FE",
  purple: "#8569CB",
  greenBg: "#DFF5E5",
  green: "#509863",
  yellowBg: "#FEF1CE",
  yellow: "#D4B45B",
  redBg: "#FEE3E2",
  red: "#D25D5A",
  white: "#FFFFFF",
  dark: "#1F2329",
};

function title(text, width = 1180) {
  return {
    type: "text",
    x: 20,
    y: 18,
    width,
    height: "fit-content",
    text,
    fontSize: 26,
    textColor: C.text,
    textAlign: "center",
  };
}

function card(id, x, y, w, h, heading, desc, border = C.blue, fill = C.white) {
  const children = [
    {
      type: "text",
      width: "fill-container",
      height: "fit-content",
      text: heading,
      fontSize: 16,
      textColor: C.text,
      textAlign: "center",
    },
  ];
  if (desc) {
    children.push({
      type: "text",
      width: "fill-container",
      height: "fit-content",
      text: desc,
      fontSize: 13,
      textColor: C.sub,
      textAlign: "center",
    });
  }
  return {
    type: "frame",
    id,
    x,
    y,
    width: w,
    height: h,
    layout: "vertical",
    gap: 8,
    padding: 14,
    justifyContent: "center",
    alignItems: "stretch",
    fillColor: fill,
    borderColor: border,
    borderWidth: 2,
    borderRadius: 8,
    children,
  };
}

function group(id, x, y, w, h, label, border, fill) {
  return {
    type: "frame",
    id,
    x,
    y,
    width: w,
    height: h,
    layout: "none",
    gap: 0,
    padding: 0,
    fillColor: fill,
    borderColor: border,
    borderWidth: 2,
    borderRadius: 10,
    children: [
      {
        type: "text",
        x: 18,
        y: 12,
        width: w - 36,
        height: "fit-content",
        text: label,
        fontSize: 18,
        textColor: C.text,
        textAlign: "center",
      },
    ],
  };
}

function pill(id, x, y, w, text, border = C.blue, fill = C.white) {
  return {
    type: "rect",
    id,
    x,
    y,
    width: w,
    height: 54,
    text,
    fontSize: 14,
    textColor: C.text,
    textAlign: "center",
    verticalAlign: "middle",
    fillColor: fill,
    borderColor: border,
    borderWidth: 2,
    borderRadius: 8,
  };
}

function diamond(id, x, y, text, border = C.yellow, fill = C.yellowBg) {
  return {
    type: "diamond",
    id,
    x,
    y,
    width: 150,
    height: 92,
    text,
    fontSize: 14,
    textColor: C.text,
    fillColor: fill,
    borderColor: border,
    borderWidth: 2,
  };
}

function cylinder(id, x, y, w, text, border = C.green, fill = C.white) {
  return {
    type: "cylinder",
    id,
    x,
    y,
    width: w,
    height: 78,
    text,
    fontSize: 14,
    textColor: C.text,
    fillColor: fill,
    borderColor: border,
    borderWidth: 2,
  };
}

function edge(from, to, opts = {}) {
  return {
    type: "connector",
    connector: {
      from,
      to,
      lineShape: opts.shape || "polyline",
      lineColor: C.line,
      lineWidth: 2,
      lineStyle: opts.style || "solid",
      endArrow: opts.endArrow || "arrow",
      label: opts.label,
      labelPosition: opts.labelPosition,
      fromAnchor: opts.fromAnchor,
      toAnchor: opts.toAnchor,
      waypoints: opts.waypoints,
    },
  };
}

function doc(nodes) {
  return { version: 2, nodes };
}

const diagrams = {
  "overall-architecture": doc([
    title("总体架构：Agent 生成 Runtime 的闭环"),
    card("entry", 60, 120, 180, 96, "启动入口", "run.sh / src/main.py", C.blue, C.blueBg),
    card("agent", 310, 120, 190, 96, "OpenAI Agent", "规划与编辑候选代码", C.purple, C.purpleBg),
    card("tools", 570, 120, 220, 96, "工具与评测", "文件编辑 / 正确性 / benchmark", C.green, C.greenBg),
    card("engine", 860, 120, 220, 96, "稳定产物", "workspace/engine.py", C.yellow, C.yellowBg),
    pill("inputs", 560, 275, 245, "model_config + weights", C.green),
    pill("official", 855, 275, 230, "官方黑盒评测", C.yellow),
    edge("entry", "agent"),
    edge("agent", "tools"),
    edge("tools", "engine", { label: "通过且更优" }),
    edge("inputs", "tools", { fromAnchor: "top", toAnchor: "bottom" }),
    edge("engine", "official", { fromAnchor: "bottom", toAnchor: "top" }),
    edge("tools", "agent", {
      label: "失败反馈",
      style: "dashed",
      fromAnchor: "top",
      toAnchor: "top",
      waypoints: [{ x: 680, y: 75 }, { x: 405, y: 75 }],
    }),
  ]),

  "agent-flow": doc([
    title("Agent 主流程：生成、验证、优化、提交"),
    card("generate", 60, 130, 185, 90, "生成候选", "创建或修改 engine", C.blue, C.blueBg),
    card("correct", 310, 130, 185, 90, "正确性测试", "logits 对齐 reference", C.purple, C.purpleBg),
    diamond("pass", 555, 125, "通过?"),
    card("bench", 760, 130, 185, 90, "吞吐评测", "prefill / decode / mixed", C.green, C.greenBg),
    diamond("better", 1000, 125, "更优?"),
    card("commit", 965, 285, 205, 88, "提交稳定版", "写入 workspace/engine.py", C.yellow, C.yellowBg),
    card("analyze", 555, 285, 215, 88, "分析瓶颈", "给出下一轮优化方向", C.red, C.redBg),
    edge("generate", "correct"),
    edge("correct", "pass"),
    edge("pass", "bench", { label: "是" }),
    edge("bench", "better"),
    edge("better", "commit", { label: "是", fromAnchor: "bottom", toAnchor: "top" }),
    edge("better", "analyze", { label: "否", fromAnchor: "bottom", toAnchor: "top" }),
    edge("analyze", "generate", {
      label: "继续编辑",
      style: "dashed",
      fromAnchor: "left",
      toAnchor: "bottom",
      waypoints: [{ x: 140, y: 330 }],
    }),
    edge("pass", "generate", {
      label: "否",
      style: "dashed",
      fromAnchor: "top",
      toAnchor: "top",
      waypoints: [{ x: 630, y: 75 }, { x: 150, y: 75 }],
    }),
  ]),

  "startup-logging-module": doc([
    title("启动与日志模块"),
    card("main", 80, 135, 180, 86, "src/main.py", "统一入口", C.blue, C.blueBg),
    card("env", 335, 135, 180, 86, "加载环境", ".env / env vars", C.purple, C.purpleBg),
    card("log", 590, 135, 210, 86, "日志准备", "备份旧日志并写 results.log", C.green, C.greenBg),
    card("run", 875, 135, 220, 86, "启动 Agent", "asyncio.run(agent_main)", C.yellow, C.yellowBg),
    edge("main", "env"),
    edge("env", "log"),
    edge("log", "run"),
  ]),

  "agent-orchestration-module": doc([
    title("Agent 编排模块"),
    card("prompt", 70, 120, 190, 86, "Prompt", "instructions + input", C.blue, C.blueBg),
    card("agent", 330, 120, 210, 86, "Agent 对象", "SDK Agent + tools", C.purple, C.purpleBg),
    card("runner", 610, 120, 190, 86, "Runner", "执行多轮工具调用", C.green, C.greenBg),
    card("gate", 870, 120, 210, 86, "退出门禁", "检查测试与 benchmark 状态", C.yellow, C.yellowBg),
    pill("hooks", 610, 285, 190, "ToolCallLogger", C.green),
    edge("prompt", "agent"),
    edge("agent", "runner"),
    edge("runner", "gate"),
    edge("runner", "hooks", { fromAnchor: "bottom", toAnchor: "top" }),
    edge("gate", "runner", {
      label: "未通过则续跑",
      style: "dashed",
      fromAnchor: "top",
      toAnchor: "top",
      waypoints: [{ x: 980, y: 70 }, { x: 700, y: 70 }],
    }),
  ]),

  "engine-file-management-module": doc([
    title("Engine 文件管理模块"),
    card("template", 70, 120, 190, 86, "模板", "engine_template.py", C.blue, C.blueBg),
    card("candidate", 330, 120, 210, 86, "候选文件", "engine_candidate.py", C.purple, C.purpleBg),
    card("edit", 610, 120, 190, 86, "编辑工具", "view / replace / append", C.green, C.greenBg),
    diamond("commit_gate", 855, 115, "通过且更优?", C.yellow, C.yellowBg),
    card("stable", 1030, 120, 190, 86, "稳定文件", "workspace/engine.py", C.yellow, C.yellowBg),
    pill("state", 600, 285, 230, "每次编辑提升 revision", C.green),
    edge("template", "candidate"),
    edge("candidate", "edit"),
    edge("edit", "commit_gate"),
    edge("commit_gate", "stable", { label: "提交" }),
    edge("edit", "state", { fromAnchor: "bottom", toAnchor: "top" }),
  ]),

  "evaluation-tool-module": doc([
    title("评测工具模块"),
    card("candidate", 80, 135, 190, 86, "候选 engine", "待验证版本", C.blue, C.blueBg),
    card("correct", 345, 80, 220, 86, "正确性测试", "public correctness", C.purple, C.purpleBg),
    card("bench", 345, 220, 220, 86, "吞吐评测", "public benchmark", C.green, C.greenBg),
    card("state", 645, 135, 210, 86, "记录状态", "revision + score", C.yellow, C.yellowBg),
    card("commit", 930, 135, 210, 86, "提交决策", "只接受正确且更快版本", C.red, C.redBg),
    edge("candidate", "correct"),
    edge("candidate", "bench"),
    edge("correct", "state"),
    edge("bench", "state"),
    edge("state", "commit"),
  ]),

  "benchmark-analysis-module": doc([
    title("Benchmark 分析模块"),
    card("json", 85, 135, 190, 86, "Benchmark JSON", "prefill / decode / mixed", C.blue, C.blueBg),
    card("metrics", 350, 135, 190, 86, "动态指标", "tokens/s 与显存", C.purple, C.purpleBg),
    card("scan", 610, 135, 200, 86, "静态扫描", "KV cache / torch.cat / full forward", C.green, C.greenBg),
    card("recommend", 885, 135, 220, 86, "优化建议", "P0-P3 下一步动作", C.yellow, C.yellowBg),
    edge("json", "metrics"),
    edge("metrics", "scan"),
    edge("scan", "recommend"),
  ]),

  "run-state-gate-module": doc([
    title("运行状态与提交门禁"),
    card("edit", 70, 135, 170, 82, "Edited", "engine_revision +1", C.blue, C.blueBg),
    card("correct", 305, 135, 180, 82, "Correct", "当前 revision 通过测试", C.purple, C.purpleBg),
    card("bench", 550, 135, 190, 82, "Benchmarked", "当前 revision 有分数", C.green, C.greenBg),
    card("commit", 805, 135, 180, 82, "Committed", "刷新 best_score", C.yellow, C.yellowBg),
    card("exit", 1040, 135, 160, 82, "Exit Ready", "门禁通过", C.red, C.redBg),
    edge("edit", "correct"),
    edge("correct", "bench"),
    edge("bench", "commit"),
    edge("commit", "exit"),
  ]),

};

for (const [name, diagram] of Object.entries(diagrams)) {
  fs.writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(diagram, null, 2) + "\n");
}

console.log(`wrote ${Object.keys(diagrams).length} whiteboard DSL diagrams`);
