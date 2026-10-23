/* One illustrative iteration. This is a teaching aid, not a simulator backend. */
(function () {
  "use strict";
  function initialiseTutorial() {
    const component = document.getElementById("tutorial-walkthrough");
    if (!component || component.dataset.tutorialReady === "true") return;
    component.dataset.tutorialReady = "true";
    const initial = Object.freeze({
      root: { visits: 13, value: 7.35 },
      children: [
        { name: "A", visits: 8, value: 3.20 },
        { name: "B", visits: 3, value: 1.35 },
        { name: "C", visits: 1, value: 0.60 }
      ],
      exploration: 1.414,
      blackEvaluation: 0.75
    });
    const stages = [
      {
        title: "Start with visits and values",
        body: "Each node stores its visit count n and accumulated value w for the player to move at that node. The root is Black and has no untried actions. Its children are White. C has an untried action.",
        equation: "Mean return = w / n lies between 0 and 1; accumulated w can exceed 1.",
        description: "Abstract three-action tree. Black root R has 13 visits and total value 7.35. Its White children are A with 8 visits and value 3.20, B with 3 visits and value 1.35, and C with 1 visit and value 0.60. The root is fully expanded. C has an untried action."
      },
      {
        title: "Select the branch worth exploring",
        body: "Select C from the fully expanded root. Its low visit count produces the largest UCB score, despite A having more visits. Selection balances the parent’s value estimate with an exploration bonus.",
        equation: "A: 1.401 · B: 1.857 · C: 2.665 → select C",
        description: "Selection highlights the path from R to C. The starting-tree UCB scores are A 1.401, B 1.857, and C 2.665. C is selected. No statistics have changed."
      },
      {
        title: "Expand one untried action",
        body: "At C, create one new child D from an untried legal action. D is Black to move and starts with zero visits and zero accumulated value. In the modeled architecture, legal-action handling is supplied by the host.",
        equation: "New child D: n = 0, w = 0.00",
        description: "Expansion creates Black child D beneath White node C. D has zero visits and zero accumulated value. The selected path is R to C to D; the existing statistics are unchanged."
      },
      {
        title: "Evaluate the new leaf",
        body: "Neural evaluation replaces a random playout. For this example only, let the evaluator return a Black value of 0.75 at D. This arbitrary number explains the update; no trained model runs in this illustration.",
        equation: "Illustrative Black value at D: v = 0.75",
        description: "The illustrative evaluator supplies a Black value of 0.75 to D. No visit or value statistics have been updated yet."
      },
      {
        title: "Back up visits and values",
        body: "Update D, C and R along the selected path. Add one visit at each node. Store 0.75 for Black at D, 0.25 for White at C, and 0.75 for Black at R. A and B do not change. A remains the most-visited root child.",
        equation: "D: 1 / 0.75 · C: 2 / 0.85 · R: 14 / 8.10  (n / w)",
        description: "Backup updates D to 1 visit and total value 0.75, C to 2 visits and total value 0.85, and R to 14 visits and total value 8.10. A remains at 8 visits and value 3.20; B remains at 3 visits and value 1.35. A is still the most-visited root child."
      }
    ];
    const stageButtons = [...component.querySelectorAll("[data-tutorial-go]")];
    const previous = document.getElementById("tutorial-previous");
    const next = document.getElementById("tutorial-next");
    let step = 0;
    const setText = (id, value) => { document.getElementById(id).textContent = value; };
    const stat = (node, visits, value) => setText("tutorial-stats-" + node, "n = " + visits + " · w = " + value.toFixed(2));
    // Scores deliberately retain the starting state at every stage.
    initial.children.forEach(function (child) {
      const q = 1 - child.value / child.visits;
      const bonus = initial.exploration * Math.sqrt(Math.log(initial.root.visits) / child.visits);
      const row = component.querySelector('[data-tutorial-score="' + child.name + '"]');
      row.querySelector('[data-tutorial-metric="q"]').textContent = q.toFixed(3);
      row.querySelector('[data-tutorial-metric="bonus"]').textContent = bonus.toFixed(3);
      row.querySelector('[data-tutorial-metric="score"]').textContent = (q + bonus).toFixed(3);
    });
    function render(newStep) {
      step = Math.min(stages.length - 1, Math.max(0, newStep));
      const stage = stages[step];
      component.dataset.tutorialStep = String(step);
      setText("tutorial-stage-count", "Step " + step + " of 4");
      setText("tutorial-stage-title", stage.title);
      setText("tutorial-stage-body", stage.body);
      setText("tutorial-stage-equation", stage.equation);
      setText("tutorial-tree-title", "One MCTS iteration: " + stage.title);
      setText("tutorial-tree-description", stage.description);
      const backedUp = step === 4;
      stat("r", initial.root.visits + (backedUp ? 1 : 0), initial.root.value + (backedUp ? initial.blackEvaluation : 0));
      stat("c", initial.children[2].visits + (backedUp ? 1 : 0), initial.children[2].value + (backedUp ? 1 - initial.blackEvaluation : 0));
      stat("d", backedUp ? 1 : 0, backedUp ? initial.blackEvaluation : 0);
      stageButtons.forEach(function (button, index) {
        if (index === step) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
      });
      previous.disabled = step === 0;
      next.disabled = step === stages.length - 1;
      next.textContent = step === 4 ? "Iteration complete" : "Next: " + ["selection", "expansion", "evaluation", "backup"][step] + " →";
    }
    stageButtons.forEach(function (button) {
      button.addEventListener("click", function () { render(Number(button.dataset.tutorialGo)); });
    });
    previous.addEventListener("click", function () { render(step - 1); });
    next.addEventListener("click", function () { render(step + 1); });
    document.getElementById("tutorial-restart").addEventListener("click", function () { render(0); });
    render(0);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialiseTutorial);
  else initialiseTutorial();
}());
