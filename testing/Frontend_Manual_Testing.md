# SmartRecipe Manual Frontend Testing

**Build:** 1st Version :D! **Date:** 10/29/26 **Tester:** ktech404

Backend/database dependent behaviour is out of scope for this check.
This is just meant to test the frontend proof of function and site navigation. Some images, information, features, etc. may be missing and/or not completely functional as a result.

## 1. Responsive layout:

**Steps:** 
1. Run the site and inspect it at approximately **375 px**(mobile), **768 px** (tablet), and compare to **1440 px** (desktop). 
2. Check the landing page, recipe search, My Recipes, and shopping list. 
3. Resize the window and inspect navigation, forms, recipe cards, buttons, and page overflow.

**Expected:** 

Content remains readable AND visible, controls are usable, layout adapts to the viewport,  no unintended overlap, clipping, or horizontal scrolling.

**Result / notes:** 

Every page of the site is responsive at each breakpoint. All features, graphics, and information is visible and interactible, and the position of elements and text stack/flex as needed.

- **Mobile breakpoints**
<div>
  <img src="images/mobile_breakpoint_1.png" alt="Mobile breakpoint 1" width="180">
  <img src="images/mobile_breakpoint_2.png" alt="Mobile breakpoint 2" width="180">
  <img src="images/mobile_breakpoint_3.png" alt="Mobile breakpoint 3" width="180">
  <img src="images/mobile_breakpoint_4.png" alt="Mobile breakpoint 4" width="180">
  <img src="images/mobile_breakpoint_5.png" alt="Mobile breakpoint 5" width="180">
</div>

- **Tablet breakpoints**
<div>
  <img src="images/tablet_breakpoint_1.png" alt="Tablet breakpoint 1" width="220">
  <img src="images/tablet_breakpoint_2.png" alt="Tablet breakpoint 2" width="220">
  <img src="images/tablet_breakpoint_3.png" alt="Tablet breakpoint 3" width="220">
  <img src="images/tablet_breakpoint_4.png" alt="Tablet breakpoint 4" width="220">
  <img src="images/tablet_breakpoint_5.png" alt="Tablet breakpoint 5" width="220">
</div>

## 2. Form input and validation messages:

**Steps:** 
1. Submit each visible form empty, then enter invalid or
incomplete values. 
2. Enter valid-looking values and submit or update them. 
3. Repeat on forms where available.

**Expected:** 

Required fields and invalid values produce clear, nearby feedback; valid-looking input is accepted by the frontend. No success message should imply data was saved to a backend when it was not.

**Result / notes:** 

A forms that take user input and/or update have input handling/validation to block blank values, and to avoid certain characters where needed. Forms also give feedback indicating the website is still under development.

- **User Account Email:**

<img src="images/user_email.png" alt="User account email" width="400">

- **Shopping List Empty Field:**

<img src="images/empty_field_shopping_list.png" alt="Empty shopping list field" width="600">

- **Validation messages:**

<img src="images/validation_message_1.png" alt="Validation message 1" width="400">
<img src="images/validation_message_2.png" alt="Validation message 1" width="400">


## 3. Add, edit, and remove ingredients locally:

**Steps:** 
1. Open the ingredient input on the recipe or shopping-list
page. 
2. Add one ingredient, then several ingredients with different
names and quantities. Or, check a box to update your choice.
3. Edit an ingredient, remove one, and try submitting an empty ingredient.

**Expected:** 

Items appear in the interface, edits and removals update the visible list, and empty input is handled sensibly. Data only needs to work in the current frontend session; database persistence is not required.

**Result / notes:** 

All of the functions for entering, updating, and checking information on all of the webpages works. Of course, the storage isn't persistent, but it works as a demo. Users are unable to enter blank values.


- **Recipe Search Page:**

<img src="images/recipe_search_adding_ingredients.png" alt="Recipe search adding ingredients" width="500">

- **Shopping Cart:**

<img src="images/shopping_cart_add_ingredients.png" alt="Shopping cart adding ingredients" width="500">

- **Account Info:**

<img src="images/update_account_info_1.png" alt="Account information update 1" width="500">

<img src="images/update_account_info_2.png" alt="Account information update 2" width="500">


## 4. Navigation and recipe links:

**Steps:** 
1. Use the site navigation and main calls to action to move
between pages. 
2. From recipe search or a recipe card, open a recipe/details page. 
3. Use available back, breadcrumb, or return links.

**Expected:** 

Links open the intended page or route; recipe links do not lead to a blank page or 404; navigation remains usable after moving between pages.

**Result / notes:**

All of the links in the nav bar and in the footer are functional. All of the links on the home page are functional as well. The links on all other pages, such as the recipe results page, functional as expected and lead to the recipe card pages. The forward and back buttons work for all sites, resulting in no blank pages or 404s. All pages are accessible from any page.



## 5. Wireframe page coverage and basic functionality:

**Steps:** 
1. Compare the running site with all **seven** wireframes. 
2. Visit each corresponding page directly and through navigation. 
3. Try the main visible interaction on each page, such as submitting a form, searching, opening a recipe, saving/removing a recipe, or changing the shopping list.

**Expected:** 

All seven pages exist, more or less match their wireframes, and their visible controls provide a meaningful frontend response. Backend-dependent actions may use temporary/local state or a clear placeholder, they should not fail silently.

**Result / notes:**

All of the 7 wireframes have been translated into functional parts of the website. There are not yet graphics/images, but the visual layout and neccesary functions are present and clear for each page. Some pages could be more clear about place holders, for example, images on  the recipe card page.

1. **Landing page:**

<img src="images/homepage_1.png" alt="Landing page screenshot 1" width="500">

<img src="images/homepage_2.png" alt="Landing page screenshot 2" width="500">

2. **User account information page:**

<img src="images/account_info.png" alt="User account information page" width="500">

3. **Recipe search page:**

<img src="images/recipe_search.png" alt="Recipe search page" width="500">

4. **Recipe search results page:**

<img src="images/recipe_search_results.png" alt="Recipe search results page" width="500">

5. **Recipe card page:**

<img src="images/recipe_card_page.png" alt="Recipe card page" width="500">

6. **My Recipes:**

<img src="images/my_recipes.png" alt="My Recipes page" width="500">

7. **Shopping list:**

<img src="images/shopping_cart.png" alt="Shopping list page" width="500">



## Testing log:

  Check: Pass / Fail / Blocked 

  1. Responsive layout: *Pass*
  2. Form validation: *Pass*
  3. Ingredient interactions: *Pass*
  4. Navigation and recipe links: *Pass*
  5. Page coverage: *Pass*
