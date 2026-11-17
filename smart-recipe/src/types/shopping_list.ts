export interface ShoppingListItem {
  id: string;
  name: string;
  quantity: string;
  checked: boolean;
  recipeId?: string;
}

export interface ShoppingListResponse {
  items: ShoppingListItem[];
}

export interface AddShoppingListItemRequest {
  name: string;
  quantity: string;
  recipeId?: string;
}
