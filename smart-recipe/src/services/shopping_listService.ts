import { apiRequest } from "@/src/api/client";
import { API_ENDPOINTS } from "@/src/api/endpoints";
import type {
  ShoppingListItem,
  ShoppingListResponse,
  AddShoppingListItemRequest,
} from "@/src/types/shopping_list";

export async function getShoppingList(): Promise<ShoppingListResponse> {
  return apiRequest<ShoppingListResponse>(
    API_ENDPOINTS.SHOPPING_LIST
  );
}

export async function addShoppingListItem(
  item: AddShoppingListItemRequest
): Promise<ShoppingListItem> {
  return apiRequest<ShoppingListItem>(
    API_ENDPOINTS.SHOPPING_LIST,
    {
      method: "POST",
      body: JSON.stringify(item),
    }
  );
}

export async function updateShoppingListItem(
  id: string,
  checked: boolean
): Promise<ShoppingListItem> {
  return apiRequest<ShoppingListItem>(
    API_ENDPOINTS.SHOPPING_LIST_ITEM(id),
    {
      method: "PATCH",
      body: JSON.stringify({ checked }),
    }
  );
}

export async function removeShoppingListItem(
  id: string
): Promise<void> {
  return apiRequest<void>(
    API_ENDPOINTS.SHOPPING_LIST_ITEM(id),
    {
      method: "DELETE",
    }
  );
}
