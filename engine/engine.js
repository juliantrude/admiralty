"use strict";
/*
 * Hliðskjálf graph engine (docs/plans/M6.md). One fixed program, one data file: a Solution Graph.
 * Everything from the JSON reaches the DOM through textContent or Cytoscape's canvas, never as HTML.
 * Layout is deterministic: sorted ids, sizes from the label alone (no DOM measuring), fixed ELK options.
 */
(function () {
  const TITLE_MAX = 40;
  const NODE_HEIGHT = 58;
  const NODE_MIN_WIDTH = 132;
  const NODE_MAX_WIDTH = 320;
  const CHAR_WIDTH = 7;
  const TAG_CHAR_WIDTH = 6;
  const NODE_PADDING = 20;
  const READABLE_ZOOM = 0.8;
  const VIEW_PADDING = 30;
  const ICON_SIZE = 44; // big enough to tell a node's theme at a glance (Julian, 2026-10-26)
  const ICON_SPACE = 56; // icon plus gap on the left of every node
  const FADED_OPACITY = 0.15;
  const NODE_TYPES = ["goal", "cause", "remedy", "obstacle"];
  const EDGE_KINDS = ["cause", "remedy", "obstacle"];
  const REQUIRED_ARRAYS = ["nodes", "edges", "circles", "key_actions", "pruned"];

  // --- pure functions -----------------------------------------------------------------------------

  function nodeLabel(title) {
    const chars = Array.from(String(title));
    return chars.length > TITLE_MAX ? chars.slice(0, TITLE_MAX - 1).join("") + "…" : chars.join("");
  }

  /** Size from the visible title and the tag line alone: no DOM measuring, so every machine gets the same layout. */
  function nodeSize(title, tag, badges) {
    const titleWidth = CHAR_WIDTH * Array.from(String(badges || "") + nodeLabel(title)).length;
    const tagWidth = TAG_CHAR_WIDTH * Array.from(String(tag || "")).length;
    const width = NODE_PADDING + ICON_SPACE + Math.max(titleWidth, tagWidth);
    return { width: Math.min(NODE_MAX_WIDTH, Math.max(NODE_MIN_WIDTH, width)), height: NODE_HEIGHT };
  }

  // Colour-blind-safe hues (Okabe-Ito without yellow and black), one per Vicious Circle in circle order.
  const CIRCLE_PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"];
  const TYPE_NAME = { goal: "Goal", cause: "Cause", remedy: "Remedy", obstacle: "Obstacle" };

  // Canvas colours per theme; engine.css holds the page's. Dark leans on the game's look: deep navy panels, teal
  // frames, warm titles. Every colour still comes with words in the node tag and the legend.
  const THEMES = {
    dark: {
      fill: { goal: "#10304a", cause: "#33260f", remedy: "#0f3324", obstacle: "#3a1419" },
      border: { goal: "#5fb0f0", cause: "#d8a548", remedy: "#46c483", obstacle: "#e0646a" },
      text: "#e3eef4",
      mutedText: "#8fa1ad",
      plain: "#0c1a28",
      edge: "#5f8ea6",
      present: "#ff6b6b",
      crisis: "#ff4d4d",
      actionable: "#5ff0a0",
      hatchLine: "#1d5a3e",
      obstructedFill: "#1b232c",
      obstructedBorder: "#4d5c68",
      ink: "#e3eef4",
      selected: "#5fd6d0",
      selectedOpacity: 0.35,
      outline: "#e8c97a",
      judgeFill: "#1f2633",
      judgeBorder: "#8c9bb0",
    },
    light: {
      fill: { goal: "#e8f0fe", cause: "#fff4e0", remedy: "#e6f4ea", obstacle: "#fde8e8" },
      border: { goal: "#3b6fb6", cause: "#a8741c", remedy: "#2f8a52", obstacle: "#b3261e" },
      text: "#1b1f24",
      mutedText: "#59606b",
      plain: "#ffffff",
      edge: "#8a93a0",
      present: "#c0392b",
      crisis: "#8a1c1c",
      actionable: "#1e8e3e",
      hatchLine: "#a9cfb4",
      obstructedFill: "#d9dce1",
      obstructedBorder: "#8a93a0",
      ink: "#1b1f24",
      selected: "#1b1f24",
      selectedOpacity: 0.18,
      outline: "#1b1f24",
      judgeFill: "#eef0f4",
      judgeBorder: "#6b7686",
    },
  };
  const THEME_KEY = "hlidskjalf-theme";
  let T = THEMES.dark;

  /** Circle id -> colour, and node id -> circle, both from circle order in the data. */
  function circleInfo(doc) {
    const color = new Map();
    const circleOf = new Map();
    doc.circles.forEach((circle, index) => {
      color.set(circle.id, CIRCLE_PALETTE[index % CIRCLE_PALETTE.length]);
      for (const member of circle.members) if (!circleOf.has(member)) circleOf.set(member, circle.id);
    });
    return { color, circleOf };
  }

  /** The second label line: type and state in words, so colour is never the only signal. */
  function tagOf(node, breakPoint) {
    const parts = [];
    if (node.source === "model") parts.push("model");
    parts.push(node.type);
    if (node.type === "goal") {
      if (node.horizon) parts.push(node.horizon);
      if (node.crisis) parts.push("CRISIS");
    }
    if (node.type === "remedy" && node.status) parts.push(node.status);
    if (node.type === "obstacle" && node.check_state) parts.push(node.check_state);
    if (breakPoint) parts.push("\u2691 break point");
    return parts.join(" \u00b7 ");
  }

  // Negative circled digits for Key Action ranks 1 to 10; beyond that the plain number.
  const RANK_DIGITS = ["\u2776", "\u2777", "\u2778", "\u2779", "\u277a", "\u277b", "\u277c", "\u277d", "\u277e", "\u277f"];
  const STATUS_BADGE = { pending: "\u23f1 ", obstructed: "\u{1F6AB} " };

  /** What stands before the title: the Key Action rank, then the Remedy state as a symbol. */
  function badgesOf(node, rank) {
    let badges = "";
    if (rank !== undefined) badges += `${RANK_DIGITS[rank - 1] || "#" + rank} `;
    if (node.type === "remedy" && STATUS_BADGE[node.status]) badges += STATUS_BADGE[node.status];
    return badges;
  }

  // Placeholder icons per node type until a node carries a game icon (docs/plans/M6-revision.md).
  const TYPE_GLYPH = { goal: "G", cause: "?", remedy: "\u2713", obstacle: "!", unchecked: "?" };
  const TYPE_INK = { goal: "#1a56c4", cause: "#a35d00", remedy: "#1e7e34", obstacle: "#b3261e", unchecked: "#6b7686" };

  function placeholderIcon(type) {
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">` +
      `<rect x="1" y="1" width="20" height="20" rx="5" fill="${TYPE_INK[type]}"/>` +
      `<text x="11" y="15.5" font-family="sans-serif" font-size="13" font-weight="700" fill="#fff" ` +
      `text-anchor="middle">${TYPE_GLYPH[type]}</text></svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }

  /** A node's icon: an embedded image from the data, else the placeholder of its type. Only data URIs of images are used. */
  function iconOf(node) {
    if (typeof node.icon === "string" && /^data:image\/(png|svg\+xml)[;,]/.test(node.icon)) return node.icon;
    const unchecked = node.type === "obstacle" && (node.check_state === "judgement" || node.check_state === "unknown");
    return placeholderIcon(unchecked ? "unchecked" : node.type);
  }

  // Impact (docs/plans/M6-revision.md): edge weights multiply along the way from a Goal, the
  // strongest way counts, and a node that serves several Goals adds them up.
  const WEIGHT_VALUE = { high: 1, medium: 0.6, low: 0.3 };
  const DEFAULT_WEIGHT = WEIGHT_VALUE.medium; // graphs composed before weights existed
  const SCALE_STEPS = [1, 1.25, 1.5];

  function edgeWeight(edge, nodeById) {
    if (WEIGHT_VALUE[edge.weight] !== undefined) return WEIGHT_VALUE[edge.weight];
    if (edge.kind === "obstacle") return 1; // clearing an Obstacle is worth what it blocks
    if (edge.kind === "remedy") {
      const strength = (nodeById.get(edge.to).ratings || {}).strength;
      if (WEIGHT_VALUE[strength] !== undefined) return WEIGHT_VALUE[strength];
    }
    return DEFAULT_WEIGHT;
  }

  /** Node id -> impact on all Goals together. Goals are the reference and are left out. */
  function impactOf(doc) {
    const nodeById = new Map(doc.nodes.map((n) => [n.id, n]));
    const edges = [...doc.edges].sort(byEdge);
    const total = new Map();
    for (const goal of doc.nodes.filter((n) => n.type === "goal").sort(byId)) {
      const best = new Map([[goal.id, 1]]);
      // weights are at most 1, so going round a Vicious Circle never raises a score: the
      // relaxation settles within as many passes as there are nodes
      for (let pass = 0; pass < doc.nodes.length; pass++) {
        let changed = false;
        for (const edge of edges) {
          if (!best.has(edge.from)) continue;
          const score = best.get(edge.from) * edgeWeight(edge, nodeById);
          if (score > (best.get(edge.to) || 0) + 1e-9) {
            best.set(edge.to, score);
            changed = true;
          }
        }
        if (!changed) break;
      }
      for (const [id, score] of best) {
        if (nodeById.get(id).type !== "goal") total.set(id, (total.get(id) || 0) + score);
      }
    }
    return total;
  }

  /** Size step 0, 1 or 2 from an impact: below a medium way, up to a strong way, beyond. */
  function scaleStep(impact) {
    if (impact >= 1) return 2;
    if (impact >= 0.55) return 1;
    return 0;
  }

  /** The chain of a node: everything it can be reached from and everything it reaches, the node included. */
  function chainOf(doc, id) {
    const chain = new Set([id]);
    for (const [from, to] of [["to", "from"], ["from", "to"]]) {
      const queue = [id];
      const seen = new Set([id]);
      while (queue.length) {
        const current = queue.shift();
        for (const edge of doc.edges) {
          if (edge[from] !== current || seen.has(edge[to])) continue;
          seen.add(edge[to]);
          chain.add(edge[to]);
          queue.push(edge[to]);
        }
      }
    }
    return chain;
  }

  function headerOf(doc) {
    const counts = {
      nodes: doc.nodes.length,
      model_nodes: doc.nodes.filter((n) => n.source === "model").length,
      circles: doc.circles.length,
      key_actions: doc.key_actions.length,
      pruned: doc.pruned.length,
    };
    const text =
      `${doc.empire} \u00b7 ${doc.date} \u00b7 ${doc.game_version} \u00b7 ${counts.nodes} nodes ` +
      `(${counts.model_nodes} model) \u00b7 ${counts.circles} Vicious Circles \u00b7 ` +
      `${counts.key_actions} Key Actions \u00b7 ${counts.pruned} pruned`;
    return { empire: doc.empire, date: doc.date, game_version: doc.game_version, counts, text };
  }

  /** Exactly the encodings that occur in this graph, each with its words. */
  function legendOf(doc) {
    const { color } = circleInfo(doc);
    const entries = [];
    const types = new Set(doc.nodes.map((n) => n.type));
    for (const type of NODE_TYPES) {
      if (types.has(type)) entries.push({ id: `type:${type}`, label: TYPE_NAME[type], fill: T.fill[type], border: T.border[type] });
    }
    const remedyStatus = {
      actionable: "green border",
      pending: "hatched, \u23f1",
      obstructed: "greyed out, \u{1F6AB}",
    };
    for (const status of Object.keys(remedyStatus)) {
      if (doc.nodes.some((n) => n.type === "remedy" && n.status === status)) {
        entries.push({
          id: `status:${status}`,
          label: `Remedy ${status} (${remedyStatus[status]})`,
          fill: T.fill.remedy,
          hatched: status === "pending",
          grey: status === "obstructed",
          border: status === "actionable" ? T.actionable : T.border.remedy,
          heavy: status === "actionable",
        });
      }
    }
    const checkLook = {
      present: "red line into it",
      unknown: "not checkable from the save, judge it yourself: grey with ?",
      judgement: "not checked against numbers, judge it yourself: grey with ?",
    };
    for (const state of Object.keys(checkLook)) {
      if (doc.nodes.some((n) => n.type === "obstacle" && n.check_state === state)) {
        entries.push({
          id: `check:${state}`,
          label: `Obstacle ${state} (${checkLook[state]})`,
          fill: state === "present" ? T.fill.obstacle : T.judgeFill,
          border: state === "present" ? T.present : T.judgeBorder,
          borderStyle: state === "unknown" || state === "judgement" ? "dotted" : "solid",
        });
      }
    }
    if (doc.nodes.some((n) => n.type !== "goal")) {
      entries.push({ id: "size", label: "bigger node = more impact on the Goals", fill: T.plain });
    }
    if (doc.edges.some((e) => e.weight)) {
      entries.push({ id: "weight", label: "edge weight: thick high, thin medium, dashed low", fill: T.plain });
    }
    if (doc.key_actions.length) {
      entries.push({ id: "rank", label: "\u2776 \u2777 \u2778 rank of a Key Action", fill: T.plain });
    }
    if (doc.nodes.some((n) => n.type === "goal" && n.crisis)) {
      entries.push({ id: "crisis", label: "Crisis Goal (heavy outline)", fill: T.fill.goal, border: T.crisis, heavy: true });
    }
    if (doc.nodes.some((n) => n.source === "model")) {
      entries.push({ id: "model", label: "Added by the model (dashed border, \u201cmodel\u201d label)", fill: T.plain, borderStyle: "dashed" });
    }
    for (const circle of doc.circles) {
      entries.push({
        id: `circle:${circle.id}`,
        label: `Vicious Circle ${circle.id} (click selects its members)`,
        circle: circle.id,
        border: color.get(circle.id),
        heavy: true,
      });
    }
    if (doc.circles.some((c) => c.break_point)) {
      entries.push({ id: "break_point", label: "\u2691 break point of a Vicious Circle (double outline)", fill: T.plain, doubleOutline: true });
    }
    return entries;
  }

  /** What the detail panel shows for a node: only fields that are in the JSON, plus links derived from its edges. */
  function panelOf(doc, id) {
    const node = doc.nodes.find((n) => n.id === id);
    if (!node) return null;
    const title = (nodeId) => (doc.nodes.find((n) => n.id === nodeId) || { title: nodeId }).title;
    const ref = (nodeId) => ({ id: nodeId, title: title(nodeId) });
    const panel = { kind: "node", id: node.id, type: node.type, source: node.source, title: node.title };
    if (node.type === "remedy") {
      panel.checked_clear = doc.edges
        .filter((e) => e.from === id && e.kind === "obstacle")
        .map((e) => doc.nodes.find((n) => n.id === e.to))
        .filter((n) => n.check_state === "clear")
        .map((n) => n.title)
        .sort();
    }
    for (const field of ["text", "horizon", "crisis", "status", "ratings", "check_state", "evidence", "rules", "reason"]) {
      if (node[field] !== undefined) panel[field] = node[field];
    }
    const action = doc.key_actions.find((a) => a.node === id);
    if (action) {
      panel.rank = action.rank;
      panel.why = action.why;
      panel.unlocks = action.unlocks.map(ref);
      panel.serves = action.serves.map(ref);
    } else if (node.type !== "goal") {
      const goals = new Set();
      const seen = new Set([id]);
      const queue = [id];
      while (queue.length) {
        const current = queue.shift();
        for (const edge of doc.edges) {
          if (edge.to !== current || seen.has(edge.from)) continue;
          seen.add(edge.from);
          queue.push(edge.from);
          if (doc.nodes.find((n) => n.id === edge.from).type === "goal") goals.add(edge.from);
        }
      }
      panel.serves = [...goals].sort().map(ref);
    }
    const label = (edge, other) => {
      const out = { ...ref(other), kind: edge.kind };
      if (edge.weight) out.weight = edge.weight;
      if (edge.weight_reason) out.weight_reason = edge.weight_reason;
      return out;
    };
    if (node.type !== "goal") panel.impact = round(impactOf(doc).get(id) || 0);
    panel.edges_in = doc.edges.filter((e) => e.to === id).sort(byEdge).map((e) => label(e, e.from));
    panel.edges_out = doc.edges.filter((e) => e.from === id).sort(byEdge).map((e) => label(e, e.to));
    const circle = doc.circles.find((c) => c.members.includes(id));
    if (circle) {
      panel.circle = circle.id;
      panel.break_point = circle.break_point === id;
    }
    return panel;
  }

  function circlePanelOf(doc, circleId) {
    const circle = doc.circles.find((c) => c.id === circleId);
    if (!circle) return null;
    const title = (nodeId) => (doc.nodes.find((n) => n.id === nodeId) || { title: nodeId }).title;
    return {
      kind: "circle",
      id: circle.id,
      title: `Vicious Circle ${circle.id}`,
      members: circle.members.map((id) => ({ id, title: title(id) })),
      break_point: circle.break_point ? { id: circle.break_point, title: title(circle.break_point) } : null,
    };
  }

  /** The first reason the document cannot be drawn, or null. */
  function validateGraph(doc) {
    if (doc === null || typeof doc !== "object" || Array.isArray(doc)) return "the data is not a JSON object";
    if (doc.schema !== 1) return `unsupported schema: ${JSON.stringify(doc.schema)} (this page reads schema 1)`;
    for (const name of REQUIRED_ARRAYS) {
      if (!Array.isArray(doc[name])) return `"${name}" is missing or not an array`;
    }
    const ids = new Set();
    for (const node of doc.nodes) {
      if (node === null || typeof node !== "object" || typeof node.id !== "string" || node.id === "") {
        return "a node has no id";
      }
      if (!NODE_TYPES.includes(node.type)) return `node ${node.id}: unknown type ${JSON.stringify(node.type)}`;
      if (typeof node.title !== "string" || node.title.trim() === "") return `node ${node.id}: no title`;
      if (ids.has(node.id)) return `node id ${node.id} occurs twice`;
      ids.add(node.id);
    }
    for (const edge of doc.edges) {
      if (edge === null || typeof edge !== "object") return "an edge is not an object";
      if (!EDGE_KINDS.includes(edge.kind)) return `edge ${edge.from} -> ${edge.to}: unknown kind ${JSON.stringify(edge.kind)}`;
      for (const end of ["from", "to"]) {
        if (!ids.has(edge[end])) return `edge ${edge.from} -> ${edge.to}: "${edge[end]}" is not a node`;
      }
    }
    for (const circle of doc.circles) {
      for (const member of circle.members || []) {
        if (!ids.has(member)) return `circle ${circle.id}: "${member}" is not a node`;
      }
    }
    for (const action of doc.key_actions) {
      if (!ids.has(action.node)) return `Key Action ${action.rank}: "${action.node}" is not a node`;
    }
    return null;
  }

  const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const edgeKey = (e) => `${e.from}\u0000${e.to}\u0000${e.kind}`;
  const byEdge = (a, b) => (edgeKey(a) < edgeKey(b) ? -1 : edgeKey(a) > edgeKey(b) ? 1 : 0);
  const round = (n) => Math.round(n * 100) / 100;

  /** Cytoscape elements in sorted order, so the input order of the JSON cannot change the layout. */
  function toElements(doc) {
    const { color, circleOf } = circleInfo(doc);
    const breakPoints = new Set(doc.circles.map((c) => c.break_point).filter(Boolean));
    const nodeById = new Map(doc.nodes.map((n) => [n.id, n]));
    const rankOf = new Map(doc.key_actions.map((a) => [a.node, a.rank]));
    const impact = impactOf(doc);
    const nodes = [...doc.nodes].sort(byId).map((node) => {
      const tag = tagOf(node, breakPoints.has(node.id));
      const badges = badgesOf(node, rankOf.get(node.id));
      const step = node.type === "goal" ? 0 : scaleStep(impact.get(node.id) || 0);
      const scale = SCALE_STEPS[step];
      const base = nodeSize(node.title, tag, badges);
      const size = { width: Math.round(base.width * scale), height: Math.round(base.height * scale) };
      const data = {
        id: node.id,
        type: node.type,
        label: `${badges}${nodeLabel(node.title)}\n${tag}`,
        tag,
        badges,
        icon: iconOf(node),
        scale,
        impact: node.type === "goal" ? null : round(impact.get(node.id) || 0),
        fontSize: Math.round(11 * scale * 10) / 10,
        iconSize: Math.round(ICON_SIZE * scale),
        textShift: Math.round((ICON_SPACE * scale) / 2),
        width: size.width,
        height: size.height,
        model: node.source === "model",
        breakPoint: breakPoints.has(node.id),
      };
      if (node.type === "remedy") data.status = node.status;
      if (node.type === "obstacle") data.checkState = node.check_state;
      if (node.type === "goal") data.crisis = node.crisis === true;
      if (rankOf.has(node.id)) data.rank = rankOf.get(node.id);
      if (circleOf.has(node.id)) data.circleColor = color.get(circleOf.get(node.id));
      return { group: "nodes", data };
    });
    const edges = [...doc.edges].sort(byEdge).map((edge) => {
      const data = { id: `${edge.from}>${edge.to}`, source: edge.from, target: edge.to, kind: edge.kind };
      if (edge.weight) data.weight = edge.weight;
      const target = nodeById.get(edge.to);
      if (edge.kind === "obstacle" && target.check_state) data.accent = target.check_state;
      const circle = circleOf.get(edge.from);
      if (circle !== undefined && circle === circleOf.get(edge.to)) data.circleColor = color.get(circle);
      return { group: "edges", data };
    });
    return [...nodes, ...edges];
  }

  /**
   * ELK layer constraints: Goals first; every other column follows from the edges alone. Key Actions are not pinned to
   * the last column: one that unblocks another (Open more job slots frees a slot for Staff more Technician jobs) must
   * stand right of it, so a chain reads as a plan, from the action on the right to the Goal on the left.
   */
  function layerConstraints(doc) {
    const constraint = new Map();
    for (const node of doc.nodes) if (node.type === "goal") constraint.set(node.id, "FIRST");
    return constraint;
  }

  const ELK_OPTIONS = {
    algorithm: "layered",
    "elk.direction": "RIGHT",
    "elk.randomSeed": "1",
    "elk.padding": "[top=20,left=20,bottom=20,right=20]",
    "elk.spacing.nodeNode": "28",
    "elk.layered.spacing.nodeNodeBetweenLayers": "90",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.layered.crossingMinimization.semiInteractive": "false",
    "elk.edgeRouting": "POLYLINE",
  };

  // --- loading ------------------------------------------------------------------------------------

  /** Data sources in order: embedded script, ?data=, sibling file. Resolves to a JSON value or undefined. */
  async function loadGraph() {
    const embedded = document.getElementById("solution-graph");
    if (embedded) return JSON.parse(embedded.textContent);
    const url = new URLSearchParams(location.search).get("data");
    for (const source of url ? [url, "solution-graph.json"] : ["solution-graph.json"]) {
      try {
        const response = await fetch(source);
        if (response.ok) return await response.json();
      } catch (_) {
        // not reachable (file://, sandbox, 404): try the next source
      }
    }
    return undefined;
  }

  // --- rendering ----------------------------------------------------------------------------------

  let cy = null;
  let current = null; // { doc, panel, selected: [ids] } of the graph on screen

  function writeState(state) {
    document.getElementById("engine-state").textContent = JSON.stringify(state);
  }

  function showError(message) {
    const box = document.getElementById("error");
    box.textContent = message;
    box.hidden = false;
  }

  function emptyState(error) {
    return { ok: false, error, nodes: [], edges: [] };
  }

  function stateOf(cyInstance, doc) {
    const circleColors = new Map(circleInfo(doc).color);
    const nodes = cyInstance
      .nodes()
      .map((node) => {
        const pos = node.position();
        const state = {
          id: node.id(),
          type: node.data("type"),
          x: round(pos.x),
          y: round(pos.y),
          width: node.data("width"),
          height: node.data("height"),
          tag: node.data("tag"),
          model: node.data("model"),
          break_point: node.data("breakPoint"),
          color: node.data("circleColor") || null,
          badges: node.data("badges"),
          scale: node.data("scale"),
          impact: node.data("impact"),
          faded: node.hasClass("faded"),
        };
        for (const [key, field] of [["status", "status"], ["check_state", "checkState"], ["crisis", "crisis"]]) {
          if (node.data(field) !== undefined) state[key] = node.data(field);
        }
        return state;
      })
      .sort(byId);
    const edges = cyInstance
      .edges()
      .not(".serves")
      .map((edge) => ({
        from: edge.data("source"),
        to: edge.data("target"),
        kind: edge.data("kind"),
        color: edge.data("circleColor") || null,
      }))
      .sort(byEdge);
    return {
      ok: true,
      error: null,
      nodes,
      edges,
      header: headerOf(current.full),
      legend: legendOf(doc).map((entry) => ({ id: entry.id, label: entry.label })),
      circles: doc.circles.map((c) => ({
        id: c.id,
        color: circleColors.get(c.id),
        members: [...c.members].sort(),
        break_point: c.break_point,
      })),
      key_actions: [...doc.key_actions]
        .sort((a, b) => a.rank - b.rank)
        .map((a) => ({ rank: a.rank, node: a.node, text: keyActionText(doc, a) })),
      pruned: doc.pruned.map((p) => ({ id: p.id, reason: p.reason })),
      theme: document.documentElement.dataset.theme,
      selected: [...current.selected].sort(),
      focus: [...current.focus].sort(),
      panel: current.panel,
    };
  }

  function publish() {
    writeState(stateOf(cy, current.doc));
  }

  const nodeTitle = (doc, id) => (doc.nodes.find((n) => n.id === id) || { title: id }).title;

  function keyActionText(doc, action) {
    const goals = action.serves.map((id) => nodeTitle(doc, id)).join(", ");
    return `${action.rank}. ${nodeTitle(doc, action.node)} — serves ${goals}. ${action.why}`;
  }

  // --- styling ------------------------------------------------------------------------------------

  function stripes(base, line) {
    const colors = [];
    const positions = [];
    const count = 10;
    for (let i = 0; i < count; i++) {
      const shade = i % 2 === 0 ? base : line;
      colors.push(shade, shade);
      positions.push(`${(i * 100) / count}%`, `${((i + 1) * 100) / count}%`);
    }
    return { colors: colors.join(" "), positions: positions.join(" ") };
  }
  function buildStyle() {
    const hatch = stripes(T.fill.remedy, T.hatchLine);
    return [
    {
      selector: "node",
      style: {
        shape: "cut-rectangle",
        width: "data(width)",
        height: "data(height)",
        label: "data(label)",
        "text-wrap": "wrap",
        "text-valign": "center",
        "text-halign": "center",
        "font-size": "data(fontSize)",
        "line-height": 1.25,
        "background-color": T.plain,
        "border-width": 1.5,
        "border-color": T.edge,
        color: T.text,
        "font-family": FONT,
        "background-image": "data(icon)",
        "background-width": "data(iconSize)",
        "background-height": "data(iconSize)",
        "background-position-x": 7,
        "background-position-y": "50%",
        "background-fit": "none",
        "background-clip": "none",
        "background-image-containment": "over",
        "text-margin-x": "data(textShift)",
      },
    },
    { selector: 'node[type = "goal"]', style: { "border-width": 2.5, "background-color": T.fill.goal, "border-color": T.border.goal } },
    { selector: 'node[type = "cause"]', style: { "background-color": T.fill.cause, "border-color": T.border.cause } },
    { selector: 'node[type = "remedy"]', style: { "background-color": T.fill.remedy, "border-color": T.border.remedy } },
    { selector: 'node[type = "obstacle"]', style: { "background-color": T.fill.obstacle, "border-color": T.border.obstacle } },
    {
      selector: 'node[status = "pending"]',
      style: {
        "background-fill": "linear-gradient",
        "background-gradient-direction": "to-bottom-right",
        "background-gradient-stop-colors": hatch.colors,
        "background-gradient-stop-positions": hatch.positions,
      },
    },
    { selector: 'node[status = "actionable"]', style: { "border-color": T.actionable, "border-width": 3 } },
    {
      selector: 'node[status = "obstructed"]',
      style: { "background-color": T.obstructedFill, color: T.mutedText, "border-color": T.obstructedBorder, "border-style": "dashed", opacity: 0.6, "background-image-opacity": 0.45 },
    },
    { selector: 'node[checkState = "present"]', style: { "border-color": T.present, "border-width": 2.5 } },
    { selector: 'node[checkState = "clear"]', style: { opacity: 0.6 } },
    {
      selector: 'node[checkState = "unknown"], node[checkState = "judgement"]',
      style: { "border-style": "dotted", "border-width": 2, "background-color": T.judgeFill, "border-color": T.judgeBorder },
    },
    { selector: "node[?crisis]", style: { "border-width": 6, "border-color": T.crisis } },
    { selector: "node[circleColor]", style: { "border-width": 5, "border-color": "data(circleColor)" } },
    { selector: "node[?model]", style: { "border-style": "dashed" } },
    {
      selector: "node[?breakPoint]",
      style: { "outline-width": 3, "outline-color": T.outline, "outline-style": "solid", "outline-offset": 3 },
    },
    { selector: "node:selected", style: { "underlay-color": T.selected, "underlay-opacity": T.selectedOpacity, "underlay-padding": 8, "underlay-shape": "round-rectangle" } },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "curve-style": "bezier",
        "line-color": T.edge,
        "target-arrow-shape": "triangle",
        "target-arrow-color": T.edge,
        "arrow-scale": 0.9,
      },
    },
    { selector: 'edge[weight = "high"]', style: { width: 3 } },
    { selector: 'edge[weight = "low"]', style: { width: 1, "line-style": "dashed" } },
    {
      selector: 'edge[accent = "present"]',
      style: { "line-color": T.present, "target-arrow-color": T.present, width: 2.5 },
    },
    { selector: 'edge[accent = "clear"]', style: { opacity: 0.45 } },
    {
      selector: 'edge[accent = "unknown"], edge[accent = "judgement"]',
      style: { "line-style": "dotted", "target-arrow-fill": "hollow" },
    },
    {
      selector: "edge[circleColor]",
      style: { width: 3.5, "line-color": "data(circleColor)", "target-arrow-color": "data(circleColor)" },
    },
    {
      selector: "edge.serves",
      style: { width: 1, "line-style": "dashed", "line-color": T.mutedText, "target-arrow-color": T.mutedText, display: "none", "curve-style": "unbundled-bezier", "control-point-distances": 60 },
    },
    { selector: "edge.serves.shown", style: { display: "element" } },
    { selector: ".faded", style: { opacity: FADED_OPACITY } },
  ];
  }

  // --- DOM: header, legend, lists, panel (text only) ----------------------------------------------

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const FONT = '"Exo 2", "Rajdhani", "Segoe UI", system-ui, sans-serif';

  function storedTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (_) {
      return null; // storage blocked: the default stands
    }
  }

  /** Dark by default; the reader's last choice wins. Page tokens via data-theme, canvas colours via THEMES. */
  function applyTheme(name) {
    const theme = THEMES[name] ? name : "dark";
    T = THEMES[theme];
    document.documentElement.dataset.theme = theme;
    const toggle = document.getElementById("theme-toggle");
    if (toggle) toggle.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    if (cy) {
      cy.style(buildStyle());
      renderLegend(current.doc);
    }
  }

  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_) {
      // not remembered, still switched
    }
    applyTheme(next);
    if (cy) publish();
  }

  function renderHeader(doc) {
    document.getElementById("header-text").textContent = headerOf(doc).text;
    document.getElementById("header").hidden = false;
  }

  function swatchOf(entry) {
    const swatch = el("span", "swatch");
    if (entry.fill) swatch.style.background = entry.fill;
    if (entry.hatched) {
      swatch.style.background = `repeating-linear-gradient(135deg, ${T.fill.remedy} 0 3px, ${T.hatchLine} 3px 6px)`;
    }
    if (entry.grey) swatch.style.background = T.obstructedFill;
    if (entry.border) swatch.style.borderColor = entry.border;
    if (entry.borderStyle) swatch.style.borderStyle = entry.borderStyle;
    if (entry.heavy) swatch.style.borderWidth = "4px";
    if (entry.muted) swatch.style.opacity = "0.6";
    if (entry.doubleOutline) swatch.style.outline = `2px solid ${T.outline}`;
    return swatch;
  }

  function renderLegend(doc) {
    const list = document.getElementById("legend");
    list.replaceChildren();
    for (const entry of legendOf(doc)) {
      const item = el("li");
      item.dataset.legend = entry.id;
      item.append(swatchOf(entry), el("span", "legend-text", entry.label));
      if (entry.circle) {
        item.classList.add("clickable");
        item.tabIndex = 0;
        item.addEventListener("click", () => selectCircle(entry.circle));
      }
      list.append(item);
    }
  }

  function renderLists(doc) {
    const actions = document.getElementById("key-actions");
    actions.replaceChildren();
    for (const action of [...doc.key_actions].sort((a, b) => a.rank - b.rank)) {
      const item = el("li", "clickable", keyActionText(doc, action).replace(/^\d+\.\s*/, ""));
      item.value = action.rank;
      item.tabIndex = 0;
      item.dataset.node = action.node;
      item.addEventListener("click", () => selectNode(action.node));
      actions.append(item);
    }
    actions.hidden = doc.key_actions.length === 0;
    const pruned = document.getElementById("pruned");
    pruned.replaceChildren();
    for (const entry of doc.pruned) pruned.append(el("li", "", `${entry.id} — ${entry.reason}`));
    document.getElementById("pruned-section").hidden = doc.pruned.length === 0;
    document.getElementById("actions-section").hidden = doc.key_actions.length === 0;
  }

  const refText = (ref) => {
    let text = ref.kind ? `${ref.title} (${ref.kind}${ref.weight ? ", " + ref.weight : ""})` : ref.title;
    if (ref.weight_reason) text += ` \u2014 ${ref.weight_reason}`;
    return text;
  };

  /** The rows of the panel as [label, [lines]]; the same panel object gives the same rows. */
  function panelRows(panel) {
    if (panel.kind === "circle") {
      const rows = [["Type", ["Vicious Circle"]], ["Members", panel.members.map(refText)]];
      rows.push(["Break point", [panel.break_point ? panel.break_point.title : "none (judgement needed)"]]);
      return rows;
    }
    const rows = [["Type", [panel.source === "model" ? `${panel.type} (added by the model)` : panel.type]]];
    if (panel.text !== undefined) rows.push(["Text", [panel.text]]);
    if (panel.horizon !== undefined) rows.push(["Horizon", [panel.horizon]]);
    if (panel.crisis) rows.push(["Crisis", ["yes"]]);
    if (panel.status !== undefined) rows.push(["Status", [panel.status]]);
    if (panel.ratings) {
      rows.push(["Ratings", [`strength ${panel.ratings.strength}`, `speed ${panel.ratings.speed}`, `cost ${panel.ratings.cost}`]]);
    }
    if (panel.checked_clear && panel.checked_clear.length) {
      rows.push(["Checked, not in the way", panel.checked_clear]);
    }
    if (panel.check_state !== undefined) rows.push(["Check state", [panel.check_state]]);
    if (panel.evidence !== undefined) rows.push(["Evidence", panel.evidence.length ? panel.evidence : ["none"]]);
    if (panel.rules !== undefined) rows.push(["Playbook Rules", panel.rules.length ? panel.rules : ["none"]]);
    if (panel.reason !== undefined) rows.push(["Reason (model)", [panel.reason]]);
    if (panel.impact !== undefined) {
      rows.push(["Impact on the Goals", [`${panel.impact} (sum over Goals of the strongest weighted way)`]]);
    }
    if (panel.rank !== undefined) rows.push(["Key Action rank", [String(panel.rank)]]);
    if (panel.why !== undefined) rows.push(["Why", [panel.why]]);
    if (panel.serves !== undefined) rows.push(["Serves", panel.serves.length ? panel.serves.map(refText) : ["no Goal"]]);
    if (panel.unlocks !== undefined) rows.push(["Unlocks", panel.unlocks.length ? panel.unlocks.map(refText) : ["nothing"]]);
    if (panel.circle !== undefined) rows.push(["Vicious Circle", [panel.circle + (panel.break_point ? " (break point)" : "")]]);
    rows.push(["Edges in", panel.edges_in.length ? panel.edges_in.map(refText) : ["none"]]);
    rows.push(["Edges out", panel.edges_out.length ? panel.edges_out.map(refText) : ["none"]]);
    return rows;
  }

  function renderPanel(panel) {
    const box = document.getElementById("panel-body");
    box.replaceChildren();
    if (!panel) {
      box.append(el("p", "hint", "Click a node, a Key Action or a Vicious Circle to see its details."));
      return;
    }
    box.append(el("h2", "", panel.title));
    const list = el("dl");
    for (const [label, lines] of panelRows(panel)) {
      list.append(el("dt", "", label));
      const value = el("dd");
      for (const line of lines) value.append(el("div", "line", line));
      list.append(value);
    }
    box.append(list);
  }

  // --- selection ------------------------------------------------------------------------------------

  function showServes(ids) {
    cy.edges(".serves").removeClass("shown");
    cy.edges(".serves").filter((edge) => ids.includes(edge.source().id()) || ids.includes(edge.target().id())).addClass("shown");
  }

  /** Focus: the chains of the selected nodes stay, everything else steps back. No selection, no focus. */
  function applyFocus(ids) {
    cy.elements().removeClass("faded");
    current.focus = new Set();
    if (!ids.length) return;
    for (const id of ids) for (const member of chainOf(current.doc, id)) current.focus.add(member);
    cy.nodes().filter((node) => !current.focus.has(node.id())).addClass("faded");
    cy.edges()
      .filter((edge) => !(current.focus.has(edge.source().id()) && current.focus.has(edge.target().id())))
      .addClass("faded");
  }

  // When a chain gets the focus, the view moves to it: the whole chain if that stays readable, else the clicked part.
  const FOCUS_MIN_ZOOM = 0.45;
  const FOCUS_MAX_ZOOM = 1.2;
  const FOCUS_PADDING = 50;
  const FOCUS_MOVE_MS = 400;

  function viewToFocus(ids) {
    if (!ids.length || !current.focus.size) return;
    const chain = cy.nodes().filter((node) => current.focus.has(node.id()));
    const box = chain.boundingBox({ includeLabels: false });
    const area = cy.container();
    const fitZoom = Math.min(
      (area.clientWidth - 2 * FOCUS_PADDING) / Math.max(1, box.w),
      (area.clientHeight - 2 * FOCUS_PADDING) / Math.max(1, box.h)
    );
    const zoom = Math.max(FOCUS_MIN_ZOOM, Math.min(FOCUS_MAX_ZOOM, fitZoom));
    // the chain fits: centre it; it does not: centre the clicked nodes, the reader pans along the chain
    const target = zoom === fitZoom || fitZoom > FOCUS_MAX_ZOOM ? box : cy.collection(ids.map((id) => cy.getElementById(id))).boundingBox();
    const pan = {
      x: area.clientWidth / 2 - ((target.x1 + target.x2) / 2) * zoom,
      y: area.clientHeight / 2 - ((target.y1 + target.y2) / 2) * zoom,
    };
    const instant = typeof window.hlidskjalfAnimationMs === "number" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    cy.stop(true, false);
    if (instant) cy.viewport({ zoom, pan });
    else cy.animate({ zoom, pan }, { duration: FOCUS_MOVE_MS });
  }

  function applySelection(ids, panel) {
    cy.nodes(":selected").unselect();
    for (const id of ids) cy.getElementById(id).select();
    current.selected = new Set(ids);
    current.panel = panel;
    applyFocus(ids);
    viewToFocus(ids);
    showServes(ids);
    renderPanel(panel);
    publish();
  }

  function selectNode(id) {
    applySelection([id], panelOf(current.full, id));
  }

  function selectCircle(circleId) {
    const circle = current.doc.circles.find((c) => c.id === circleId);
    applySelection(circle.members, circlePanelOf(current.doc, circleId));
  }

  function clearSelection() {
    applySelection([], null);
  }

  /** The seam for the driver: emits the same `tap` event a click on the node produces. */
  function click(id) {
    cy.getElementById(id).emit("tap");
  }

  // --- drawing --------------------------------------------------------------------------------------

  function addServesEdges(doc) {
    const edges = [];
    for (const action of doc.key_actions) {
      for (const goal of action.serves) {
        edges.push({
          group: "edges",
          classes: "serves",
          data: { id: `serves:${action.node}>${goal}`, source: action.node, target: goal, kind: "serves" },
        });
      }
    }
    cy.add(edges);
  }

  /** Fitting a 50 node graph into the stage shrinks the 11 px labels to about 5 px: below this zoom the view starts at the
   *  top left of the graph at a readable size instead, and the reader pans (drag) or zooms (wheel). Positions are untouched. */
  function readableView() {
    if (cy.zoom() >= READABLE_ZOOM) return;
    const box = cy.elements().boundingBox();
    cy.zoom(READABLE_ZOOM);
    cy.pan({ x: VIEW_PADDING - box.x1 * READABLE_ZOOM, y: VIEW_PADDING - box.y1 * READABLE_ZOOM });
  }

  function draw(doc, full) {
    cy = cytoscape({
      container: document.getElementById("cy"),
      elements: toElements(doc),
      style: buildStyle(),
      layout: { name: "preset" },
      autoungrabify: true,
      boxSelectionEnabled: false,
    });
    current = { doc, full, panel: null, selected: new Set(), focus: new Set() };
    renderHeader(full);
    renderLegend(doc);
    renderLists(doc);
    renderPanel(null);
    cy.on("tap", "node", (event) => selectNode(event.target.id()));
    cy.on("tap", (event) => {
      if (event.target === cy) clearSelection();
    });
    const constraint = layerConstraints(doc);
    const started = performance.now();
    cy.layout({
      name: "elk",
      animate: false,
      fit: true,
      padding: VIEW_PADDING,
      elk: ELK_OPTIONS,
      nodeLayoutOptions: (node) => {
        const layer = constraint.get(node.id());
        return layer ? { "elk.layered.layering.layerConstraint": layer } : {};
      },
      stop: () => {
        window.engineLayoutMs = Math.round(performance.now() - started);
        readableView();
        addServesEdges(doc);
        publish();
        document.dispatchEvent(new CustomEvent("engine-ready"));
      },
    }).run();
  }

  /**
   * The graph that is drawn: Obstacles the code checked against the numbers and found clear are not in the way, so
   * they leave the picture (with their edges) and are listed in their Remedy's details instead.
   */
  function drawnPart(doc) {
    const clear = new Set(doc.nodes.filter((n) => n.type === "obstacle" && n.check_state === "clear").map((n) => n.id));
    if (!clear.size) return doc;
    return {
      ...doc,
      nodes: doc.nodes.filter((n) => !clear.has(n.id)),
      edges: doc.edges.filter((e) => !clear.has(e.from) && !clear.has(e.to)),
    };
  }

  function render(doc) {
    const problem = validateGraph(doc);
    if (problem) {
      showError(`This is not a Solution Graph this page can draw: ${problem}`);
      writeState(emptyState(problem));
      return;
    }
    draw(drawnPart(doc), doc);
  }

  function offerPicker() {
    document.getElementById("loader").hidden = false;
    writeState(emptyState("no data"));
    const picker = document.getElementById("picker");
    const read = (file) => {
      if (!file) return;
      file.text().then((text) => {
        document.getElementById("loader").hidden = true;
        document.getElementById("error").hidden = true;
        try {
          render(JSON.parse(text));
        } catch (err) {
          showError(`${file.name} is not valid JSON: ${err.message}`);
          writeState(emptyState("invalid JSON"));
        }
      });
    };
    picker.addEventListener("change", () => read(picker.files[0]));
    document.addEventListener("dragover", (event) => event.preventDefault());
    document.addEventListener("drop", (event) => {
      event.preventDefault();
      read(event.dataTransfer.files[0]);
    });
  }

  async function start() {
    applyTheme(storedTheme() || "dark");
    document.getElementById("theme-toggle").addEventListener("click", toggleTheme);
    // the canvas draws its labels once; redraw them when the web font has arrived
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => cy && cy.style().update());
    let doc;
    try {
      doc = await loadGraph();
    } catch (err) {
      showError(`The data is not valid JSON: ${err.message}`);
      writeState(emptyState("invalid JSON"));
      return;
    }
    if (doc === undefined) offerPicker();
    else render(doc);
  }

  /** Same seam for the background: a tap on the canvas outside any node. */
  function clickBackground() {
    cy.emit("tap");
  }

  window.HlidskjalfEngine = {
    nodeLabel, nodeSize, validateGraph, toElements, layerConstraints, chainOf, badgesOf, iconOf, impactOf, scaleStep,
    tagOf, headerOf, legendOf, panelOf, circlePanelOf, click, clickBackground,
  };
  start();
})();
