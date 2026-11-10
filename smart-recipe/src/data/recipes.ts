// These are FAKE recipes for testing the search results function.

export type Recipe = {
  id: string;
  slug: string;
  name: string;
  image: string;
  description: string;
  time: number;
  servings: number;
  cuisine: string;
  rating: number;
  ingredients: {
    quantity: string;
    name: string;
  }[];
  instructions: string[];
};

export const recipes: Recipe[] = [
  {
    id: "1",
    slug: "lemon-garlic-chicken",
    name: "Lemon Garlic Chicken",
    image: "/images/lemon-garlic-chicken.jpg",
    description:
      "A bright, savoury chicken dish with lemon, garlic, and fresh herbs.",
    time: 25,
    servings: 2,
    cuisine: "Mediterranean",
    rating: 4.6,
    ingredients: [
      { quantity: "2", name: "chicken breasts" },
      { quantity: "1", name: "lemon" },
      { quantity: "3 cloves", name: "garlic" },
      { quantity: "1 tbsp", name: "olive oil" },
      { quantity: "1 tsp", name: "fresh thyme" },
      { quantity: "To taste", name: "salt and pepper" },
    ],
    instructions: [
      "Season the chicken with salt, pepper, and thyme.",
      "Heat olive oil in a pan over medium heat.",
      "Cook the chicken until golden and cooked through.",
      "Add the garlic and lemon juice, then cook briefly until fragrant.",
      "Check the chicken is fully cooked before serving.",
    ],
  },
  {
    id: "2",
    slug: "vegetable-pasta",
    name: "Roasted Vegetable Pasta",
    image: "/images/vegetable-pasta.jpg",
    description:
      "A comforting pasta dish with roasted vegetables and herbs.",
    time: 35,
    servings: 2,
    cuisine: "Italian",
    rating: 4.5,
    ingredients: [
      { quantity: "200 g", name: "pasta" },
      { quantity: "1", name: "courgette" },
      { quantity: "1", name: "red pepper" },
      { quantity: "2 tbsp", name: "olive oil" },
      { quantity: "To taste", name: "salt and pepper" },
    ],
    instructions: [
      "Preheat the oven to 200°C.",
      "Chop the vegetables and toss them with olive oil and seasoning.",
      "Roast until tender and lightly browned.",
      "Cook the pasta according to its packet instructions.",
      "Combine the pasta and vegetables, then serve.",
    ],
  },
  {
    id: "3",
    slug: "black-bean-tacos",
    name: "Black Bean Tacos",
    image: "/images/black-bean-tacos.jpg",
    description:
      "Easy, colourful tacos with black beans, lime, and fresh toppings.",
    time: 20,
    servings: 2,
    cuisine: "Mexican",
    rating: 4.7,
    ingredients: [
      { quantity: "1 can", name: "black beans, drained" },
      { quantity: "6", name: "corn tortillas" },
      { quantity: "1", name: "lime" },
      { quantity: "1", name: "avocado" },
      { quantity: "To taste", name: "coriander and seasoning" },
    ],
    instructions: [
      "Warm the black beans in a pan with your chosen seasoning.",
      "Heat the tortillas in a dry pan.",
      "Mash or slice the avocado and prepare the lime.",
      "Fill the tortillas with beans and toppings.",
      "Finish with lime juice and fresh coriander.",
    ],
  },
];
