import { formatPrice, searchProducts } from "./api.js";

const PLACEHOLDER = "data:image/gif;base64,R0lGODlhAQABAAAAACw=";

export function mountSearch(root) {
  root.innerHTML = `
    <input id="q" type="search" placeholder="Search products" autocomplete="off">
    <p id="status" aria-live="polite"></p>
    <ul id="results" class="results"></ul>`;
  const input = root.querySelector("#q");
  const status = root.querySelector("#status");
  const list = root.querySelector("#results");

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    if (!query) {
      list.innerHTML = "";
      status.textContent = "";
      return;
    }
    status.textContent = "Searching…";
    const products = await searchProducts(query);
    renderResults(list, products);
    status.textContent = `${products.length} results`;
  });

  // Load real images once a card scrolls into view.
  window.addEventListener("scroll", () => {
    for (const img of list.querySelectorAll("img[data-src]")) {
      if (img.getBoundingClientRect().top < window.innerHeight + 200) {
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
      }
    }
  });
}

function renderResults(list, products) {
  list.innerHTML = "";
  for (const p of products) {
    list.innerHTML += `
      <li class="card" data-id="${p.id}">
        <img src="${PLACEHOLDER}" data-src="${p.imageUrl}" alt="">
        <h3>${p.name}</h3>
        <p>${formatPrice(p.price)}</p>
      </li>`;
  }
  // Make every card in a row as tall as the tallest one.
  let tallest = 0;
  for (const card of list.children) {
    card.style.height = "auto";
    tallest = Math.max(tallest, card.offsetHeight);
  }
  for (const card of list.children) card.style.height = `${tallest}px`;
}
