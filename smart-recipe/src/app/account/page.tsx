
"use client";

import { useState } from "react";

const preferenceOptions = [
  "Vegetarian",
  "Vegan",
  "Gluten-free",
  "Dairy-free",
  "High protein",
  "Keto",
  "No pork",
  "Halal",
];

//we'll add more than these ofc. should users be able to enter cuisines?
const cuisineOptions = [
  "Italian",
  "Asian",
  "Mexican",
  "Mediterranean",
  "Indian",
  "Middle Eastern",
];

export default function AccountPage() {
  const [username, setUsername] = useState("username");
  const [email, setEmail] = useState("user@email.com");
  const [editing, setEditing] = useState(false);
  const [ingredientName, setIngredientName] = useState("");
  const [ingredients, setIngredients] = useState([
    "Chicken breast",
    "Rice",
    "Garlic",
    "Olive oil",
    "Eggs",
    "Lemon",
  ]);
  const [allergies, setAllergies] = useState(["Peanuts"]);
  const [preferences, setPreferences] = useState(["High protein"]);
  const [cuisines, setCuisines] = useState([
    "Italian",
    "Mediterranean",
  ]);
  const [message, setMessage] = useState("");

  function addIngredient(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const value = ingredientName.trim();
    if (!value) return;

    if (
      ingredients.some(
        (item) => item.toLowerCase() === value.toLowerCase()
      )
    ) {
      setMessage(`${value} is already in your ingredients.`);
      return;
    }

    setIngredients((current) => [...current, value]);
    setIngredientName("");
    setMessage(`${value} added to your ingredients.`);
  }

  function removeIngredient(name: string) {
    setIngredients((current) =>
      current.filter((item) => item !== name)
    );
  }

  function toggleOption(
    value: string,
    selected: string[],
    setSelected: (next: string[]) => void
  ) {
    setSelected(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
    );
  }

  function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEditing(false);
    setMessage("Profile changes updated in this demo.");
  }

const [newAllergy, setNewAllergy] = useState("");

function addAllergy() {
  const ingredient = newAllergy.trim();

  if (!ingredient) return;

  // Avoids duplicate entries (case-insensitive).
  if (
    allergies.some(
      (allergy) => allergy.toLowerCase() === ingredient.toLowerCase()
    )
  ) {
    setNewAllergy("");
    return;
  }

  setAllergies((current) => [...current, ingredient]);
  setNewAllergy("");
}

function removeAllergy(ingredient: string) {
  setAllergies((current) =>
    current.filter((allergy) => allergy !== ingredient)
  );
}

  return (
    <div className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR PERSONAL KITCHEN</span>
        <h1>Account &amp; preferences</h1>
        <p>
          Keep your account details, ingredients and food preferences up to date.
        </p>
      </div>

      <div className="account-layout">
        <aside className="account-sidebar">
          <section className="panel profile-card">
            <div className="profile-avatar" aria-hidden="true">
              {username.charAt(0).toUpperCase() || "U"}
            </div>
            <h2>{username}</h2>
            <p className="muted">{email}</p>
            <span className="profile-status">Demo profile</span>
          </section>

          <section className="panel account-details">
            <div className="panel-heading">
              <h2>Account information</h2>
            </div>

            {editing ? (
              <form onSubmit={saveProfile}>
                <div className="field-group">
                  <label htmlFor="account-username">Username</label>
                  <input
                    id="account-username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    required
                  />
                </div>

                <div className="field-group">
                  <label htmlFor="account-email">Email</label>
                  <input
                    id="account-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </div>

                <button
                  className="button button-primary button-full"
                  type="submit"
                >
                  Save changes
                </button>
                <button
                  className="button button-secondary button-full"
                  type="button"
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </button>
              </form>
            ) : (
              <>
                <div className="detail-row">
                  <span>Username</span>
                  <strong>{username}</strong>
                </div>
                <div className="detail-row">
                  <span>Email</span>
                  <strong className="detail-email">{email}</strong>
                </div>
                <div className="detail-row">
                    {/*will add option to change/reset password once auth handling is settled. */}
                  <span>Password</span>
                  <strong>••••••••</strong>
                </div>

                <button
                  type="button"
                  className="button button-primary button-full"
                  onClick={() => setEditing(true)}
                >
                  Edit account details
                </button>
              </>
            )}

            <button
              type="button"
              className="button button-secondary button-full"
              onClick={() =>
                setMessage(
                  "Still working on backend! bear with us :)"
                )
              }
            >
              Sign out
            </button>

            <button
              type="button"
              className="text-button danger-text button-full"
              onClick={() =>
                //once we're actually set up, there should be a confimation diaglouge here.
                setMessage(
                  "backend under construction lol"
                )
              }
            >
              Delete account
            </button>
          </section>
        </aside>

        <div className="account-main">
          <section className="panel account-section">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">YOUR KITCHEN</span>
                <h2>Owned ingredients</h2>
              </div>
              <span className="count-badge">
                {ingredients.length} items
              </span>
            </div>

            <p className="muted">
              Keep track of ingredients you already have and pantry staples. These can
              eventually be used to find matching recipes.
            </p>

            <form className="account-add-form" onSubmit={addIngredient}>
              <label className="sr-only" htmlFor="owned-ingredient">
                Add an ingredient
              </label>
              <input
                id="owned-ingredient"
                value={ingredientName}
                onChange={(event) => setIngredientName(event.target.value)}
                placeholder="Search or add an ingredient..."
              />
              <button className="button button-primary" type="submit">
                + Add
              </button>
            </form>

            {message && (
              <p className="inline-message" role="status">
                {message}
              </p>
            )}

            <div className="owned-ingredient-list">
              {ingredients.map((ingredient) => (
                <div className="owned-ingredient" key={ingredient}>
                  <span>
                    <span className="ingredient-dot" />
                    {ingredient}
                  </span>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove ${ingredient}`}
                    onClick={() => removeIngredient(ingredient)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="panel account-section">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">YOUR FOOD NEEDS</span>
                <h2>Dietary preferences</h2>
              </div>
            </div>
            <p className="muted">
              Select the preferences you want recipe suggestions to take into account.
            </p>

            <div className="preference-options">
              {preferenceOptions.map((option) => (
                <label className="check-option" key={option}>
                  <input
                    type="checkbox"
                    checked={preferences.includes(option)}
                    onChange={() =>
                      toggleOption(option, preferences, setPreferences)
                    }
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="panel account-section">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">IMPORTANT TO KNOW</span>
                <h2>Allergies &amp; intolerances</h2>
              </div>
            </div>
            <p className="muted">
              Record ingredients that recipes should avoid.
            </p>
            
            <div className="allergy-input-group">
            <form
                className="allergy-entry"
                onSubmit={(event) => {
                event.preventDefault();
                addAllergy();
                }}
            >
                <label className="sr-only" htmlFor="new-allergy">
                Ingredient to avoid
                </label>
                <input
                id="new-allergy"
                type="text"
                value={newAllergy}
                onChange={(event) => setNewAllergy(event.target.value)}
                placeholder="Enter an ingredient, e.g. mustard"
                />
                <button
                type="submit"
                className="button button-primary"
                disabled={!newAllergy.trim()}
                >
                + Add
                </button>
            </form>

            <div className="preference-options">
                {allergies.map((ingredient) => (
                <div className="check-option" key={ingredient}>
                    <span>{ingredient}</span>
                    <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove ${ingredient} from ingredients to avoid`}
                    onClick={() => removeAllergy(ingredient)}
                    >
                    ×
                    </button>
                </div>
                ))}

                {allergies.length === 0 && (
                <p className="muted">
                    No ingredients added yet.
                </p>
                )}
            </div>
            </div>


            <p className="helper-text">
             {/*keep in mind all these preferences should be stored in the database+used for searching. right now they're just preferences stored in page states */}
            </p>
          </section>

          <section className="panel account-section">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">FLAVOURS YOU LOVE</span>
                <h2>Preferred cuisines</h2>
              </div>
            </div>

            <div className="preference-options">
              {cuisineOptions.map((option) => (
                <label className="check-option" key={option}>
                  <input
                    type="checkbox"
                    checked={cuisines.includes(option)}
                    onChange={() =>
                      toggleOption(option, cuisines, setCuisines)
                    }
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
          </section>

          <div className="account-save-row">
        
            <button
              className="button button-primary"
              type="button"
              onClick={() =>
                setMessage(
                  "Preferences are updated, but will actually be stored once backend is ready"
                )
              }
            >
              Save preferences
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
