
"use client";

import { useState } from "react";

type ShoppingItem = {
  id: number;
  name: string;
  quantity: string;
  source: string;
  checked: boolean;
};

type CartRecipe = {
  id: number;
  name: string;
  ingredientCount: number;
};

//will update attributes to more accurate reflect recipe content later.
const initialItems: ShoppingItem[] = [
  { id: 1, name: "Lemon", quantity: "2", source: "Lemon garlic chicken", checked: false },
  { id: 2, name: "Garlic", quantity: "9 cloves", source: "2 recipes", checked: false },
  { id: 3, name: "Fresh thyme", quantity: "1 tsp", source: "Lemon garlic chicken", checked: false },
  { id: 4, name: "Spaghetti", quantity: "400 g", source: "Spaghetti aglio e olio", checked: false },
  { id: 5, name: "Black beans", quantity: "2 cans", source: "Black bean tacos", checked: false },
  { id: 6, name: "Corn tortillas", quantity: "8", source: "Black bean tacos", checked: false },
  { id: 7, name: "Paper towels", quantity: "1 pack", source: "Added manually", checked: false },
];

const initialCart: CartRecipe[] = [
  { id: 1, name: "Lemon garlic chicken", ingredientCount: 6 },
  { id: 2, name: "Spaghetti aglio e olio", ingredientCount: 5 },
  { id: 3, name: "Black bean tacos", ingredientCount: 7 },
];

export default function ShoppingListPage() {
  const [items, setItems] = useState(initialItems);
  const [cart, setCart] = useState(initialCart);
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState("whole");

  function addItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;

    setItems((current) => [
      ...current,
      {
        id: Date.now(),
        name: name.trim(),
        quantity: `${quantity || "1"}${unit === "whole" ? "" : ` ${unit}`}`,
        source: "Added manually",
        checked: false,
      },
    ]);

    setName("");
    setQuantity("1");
    setUnit("whole");
  }

  function toggleItem(id: number) {
    setItems((current) =>
      current.map((item) =>
        item.id === id
          ? { ...item, checked: !item.checked }
          : item
      )
    );
  }

  function removeItem(id: number) {
    setItems((current) => current.filter((item) => item.id !== id));
  }

  function removeRecipe(recipe: CartRecipe) {
    setCart((current) =>
      current.filter((item) => item.id !== recipe.id)
    );

    setItems((current) =>
      current.filter((item) => item.source !== recipe.name)
    );
  }

  const checkedCount = items.filter((item) => item.checked).length;

  return (
    <div className="page-container">
      <div className="page-heading">
        <span className="eyebrow">READY FOR YOUR NEXT SHOP</span>
        <h1>Shopping list</h1>
        <p>
          Keep track of ingredients for your planned meals and everyday essentials.
        </p>
      </div>

      <form className="panel add-shopping-item" onSubmit={addItem}>
        <div className="shopping-add-name">
          <label htmlFor="shopping-name">Ingredient</label>
          <input
            id="shopping-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Add an ingredient to your list"
            required
          />
        </div>

        <div className="shopping-add-quantity">
          <label htmlFor="shopping-quantity">Quantity</label>
          <input
            id="shopping-quantity"
            type="number"
            min="0.1"
            step="any"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </div>

        <div className="shopping-add-unit">
          <label htmlFor="shopping-unit">Unit</label>
          <select
            id="shopping-unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
          >
            <option value="whole">Whole / items</option>
            <option value="g">g</option>
            <option value="kg">kg</option>
            <option value="ml">ml</option>
            <option value="litres">litres</option>
            <option value="cups">cups</option>
            <option value="cans">cans</option>
            <option value="packs">packs</option>
          </select>
        </div>

        <button type="submit" className="button button-primary">
          + Add item
        </button>
      </form>

      <div className="shopping-layout">
        <section className="panel shopping-cart-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">MEAL PLANNING</span>
              <h2>Recipes in cart</h2>
            </div>
            <span className="count-badge">{cart.length}</span>
          </div>

          {cart.map((recipe) => (
            <div className="cart-recipe-row" key={recipe.id}>
              <div>
                <h3>{recipe.name}</h3>
                <p className="muted">
                  {recipe.ingredientCount} ingredients
                </p>
              </div>
              <button
                type="button"
                className="text-button danger-text"
                onClick={() => removeRecipe(recipe)}
              >
                Remove
              </button>
            </div>
          ))}

          {cart.length === 0 && (
            <p className="empty-message">
              No recipes in your cart yet.
            </p>
          )}

          <p className="helper-text">
            Removing a recipe also removes ingredients listed exclusively
            under that recipe.
          </p>
        </section>

        <section className="panel shopping-items-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">YOUR CHECKLIST</span>
              <h2>Ingredients</h2>
            </div>
            <span className="count-badge">
              {checkedCount} of {items.length} checked
            </span>
          </div>

          <div className="shopping-progress">
            <div
              className="shopping-progress-fill"
              style={{
                width: `${items.length ? (checkedCount / items.length) * 100 : 0}%`,
              }}
            />
          </div>

          {items.map((item) => (
            <div
              className={`shopping-item-row ${item.checked ? "item-checked" : ""}`}
              key={item.id}
            >
              <label className="shopping-item-label">
                <input
                  type="checkbox"
                  checked={item.checked}
                  onChange={() => toggleItem(item.id)}
                />
                <span className="ingredient-name">{item.name}</span>
              </label>

              <span className="shopping-quantity">
                {item.quantity}
              </span>

              <span className="source-tag">{item.source}</span>

              <button
                type="button"
                className="icon-button"
                aria-label={`Remove ${item.name}`}
                onClick={() => removeItem(item.id)}
              >
                ×
              </button>
            </div>
          ))}

          {items.length === 0 && (
            <div className="empty-state">
              <h3>Your list is empty</h3>
              <p>Add an ingredient using the form above.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
