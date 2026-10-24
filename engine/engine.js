"use strict";
/*
 * Hliðskjálf graph engine (docs/plans/M6.md). One fixed program, one data file: a Solution Graph.
 * Everything from the JSON reaches the DOM through textContent or Cytoscape's canvas, never as HTML.
 * Layout is deterministic: sorted ids, sizes from the label alone (no DOM measuring), fixed ELK options.
 */
(function () {
  const TITLE_MAX = 40;
  const NODE_HEIGHT = 40;
  const NODE_MIN_WIDTH = 96;
  const NODE_MAX_WIDTH = 320;
  const CHAR_WIDTH = 7;
  const NODE_PADDING = 20;
  const NODE_TYPES = ["goal", "cause", "remedy", "obstacle"];
  const EDGE_KINDS = ["cause", "remedy", "obstacle"];
  const REQUIRED_ARRAYS = ["nodes", "edges", "circles", "key_actions", "pruned"];

  // --- pure functions -----------------------------------------------------------------------------

  function nodeLabel(title) {
    const chars = Array.from(String(title));
    return chars.length > TITLE_MAX ? chars.slice(0, TITLE_MAX - 1).join("") + "…" : chars.join("");
  }

  function nodeSize(title) {
    const width = NODE_PADDING + CHAR_WIDTH * Array.from(nodeLabel(title)).length;
    return { width: Math.min(NODE_MAX_WIDTH, Math.max(NODE_MIN_WIDTH, width)), height: NODE_HEIGHT };
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
    const nodes = [...doc.nodes].sort(byId).map((node) => {
      const size = nodeSize(node.title);
      return {
        group: "nodes",
        data: { id: node.id, type: node.type, label: nodeLabel(node.title), width: size.width, height: size.height },
      };
    });
    const edges = [...doc.edges].sort(byEdge).map((edge) => ({
      group: "edges",
      data: { id: `${edge.from}>${edge.to}`, source: edge.from, target: edge.to, kind: edge.kind },
    }));
    return [...nodes, ...edges];
  }

  /** ELK layer constraints: Goals first, Key Actions last, everything else in between. */
  function layerConstraints(doc) {
    const constraint = new Map();
    for (const node of doc.nodes) if (node.type === "goal") constraint.set(node.id, "FIRST");
    for (const action of doc.key_actions) constraint.set(action.node, "LAST");
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

  function stateOf(cyInstance) {
    const nodes = cyInstance
      .nodes()
      .map((node) => {
        const pos = node.position();
        return {
          id: node.id(),
          type: node.data("type"),
          x: round(pos.x),
          y: round(pos.y),
          width: node.data("width"),
          height: node.data("height"),
        };
      })
      .sort(byId);
    const edges = cyInstance
      .edges()
      .map((edge) => ({ from: edge.data("source"), to: edge.data("target"), kind: edge.data("kind") }))
      .sort(byEdge);
    return { ok: true, error: null, nodes, edges };
  }

  const STYLE = [
    {
      selector: "node",
      style: {
        shape: "round-rectangle",
        width: "data(width)",
        height: "data(height)",
        label: "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        "font-size": 12,
        "background-color": "#ffffff",
        "border-width": 1.5,
        "border-color": "#5b6573",
        color: "#1b1f24",
      },
    },
    { selector: 'node[type = "goal"]', style: { "border-width": 2.5, "background-color": "#e8f0fe" } },
    { selector: 'node[type = "cause"]', style: { "background-color": "#fff4e0" } },
    { selector: 'node[type = "remedy"]', style: { "background-color": "#e6f4ea" } },
    { selector: 'node[type = "obstacle"]', style: { "background-color": "#fde8e8" } },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "curve-style": "bezier",
        "line-color": "#8a93a0",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "#8a93a0",
        "arrow-scale": 0.9,
      },
    },
  ];

  function draw(doc) {
    cy = cytoscape({
      container: document.getElementById("cy"),
      elements: toElements(doc),
      style: STYLE,
      layout: { name: "preset" },
      autoungrabify: true,
      boxSelectionEnabled: false,
    });
    const constraint = layerConstraints(doc);
    const started = performance.now();
    cy.layout({
      name: "elk",
      animate: false,
      fit: true,
      padding: 30,
      elk: ELK_OPTIONS,
      nodeLayoutOptions: (node) => {
        const layer = constraint.get(node.id());
        return layer ? { "elk.layered.layering.layerConstraint": layer } : {};
      },
      stop: () => {
        window.engineLayoutMs = Math.round(performance.now() - started);
        writeState(stateOf(cy));
      },
    }).run();
  }

  function render(doc) {
    const problem = validateGraph(doc);
    if (problem) {
      showError(`This is not a Solution Graph this page can draw: ${problem}`);
      writeState(emptyState(problem));
      return;
    }
    draw(doc);
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

  window.HlidskjalfEngine = { nodeLabel, nodeSize, validateGraph, toElements, layerConstraints };
  start();
})();
