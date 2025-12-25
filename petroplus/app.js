(function () {
  const q = document.getElementById("q");
  const clearBtn = document.getElementById("clearBtn");
  const nodes = Array.from(document.querySelectorAll(".searchable"));

  function norm(s) { return (s || "").toLowerCase().trim(); }

  function apply() {
    const term = norm(q.value);
    if (!term) {
      nodes.forEach(n => n.classList.remove("hidden"));
      return;
    }

    nodes.forEach(n => {
      const tags = norm(n.getAttribute("data-tags"));
      const text = norm(n.innerText);
      const hit = tags.includes(term) || text.includes(term);
      n.classList.toggle("hidden", !hit);
    });
  }

  q.addEventListener("input", apply);
  clearBtn.addEventListener("click", () => { q.value = ""; apply(); q.focus(); });

  // initial
  apply();
})();
