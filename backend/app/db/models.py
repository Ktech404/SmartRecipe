from datetime import datetime, date
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, ForeignKey,
                        Index, Integer, Numeric, Text, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import CITEXT, ARRAY, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from .session import Base

TS = TIMESTAMP(timezone=True)


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(CITEXT, unique=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredient"
    ingredient_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, unique=True)
    category: Mapped[str | None] = mapped_column(Text)
    is_staple: Mapped[bool] = mapped_column(Boolean, server_default="false")


class IngredientSynonym(Base):
    __tablename__ = "ingredient_synonym"
    synonym_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.ingredient_id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(CITEXT, unique=True)


class Preference(Base):
    __tablename__ = "preference"
    __table_args__ = (
        UniqueConstraint("name", "type"),
        CheckConstraint("type IN ('dietary','cuisine')"),
    )
    preference_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT)
    type: Mapped[str] = mapped_column(Text)


class UserPreference(Base):
    __tablename__ = "user_preference"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    preference_id: Mapped[int] = mapped_column(
        ForeignKey("preference.preference_id", ondelete="CASCADE"), primary_key=True)


class UserRestricted(Base):
    __tablename__ = "user_restricted"
    __table_args__ = (CheckConstraint("restriction_type IN ('allergy','blacklist')"),)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.ingredient_id", ondelete="CASCADE"), primary_key=True)
    restriction_type: Mapped[str] = mapped_column(Text)


class UserInventory(Base):
    __tablename__ = "user_inventory"
    __table_args__ = (
        UniqueConstraint("user_id", "ingredient_id"),
        CheckConstraint("shelf_life_type IN ('perishable','long_life')"),
    )
    inventory_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.ingredient_id"))
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(Text)
    shelf_life_type: Mapped[str] = mapped_column(Text, server_default="long_life")
    expiration_date: Mapped[date | None] = mapped_column(Date)
    added_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Recipe(Base):
    __tablename__ = "recipe"
    recipe_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, unique=True)
    generated_tag: Mapped[bool] = mapped_column(Boolean, server_default="false")
    total_minutes: Mapped[int | None] = mapped_column(Integer)
    servings: Mapped[int | None] = mapped_column(Integer)
    rating_avg: Mapped[float | None] = mapped_column(Numeric(2, 1))
    rating_count: Mapped[int | None] = mapped_column(Integer)
    cuisine: Mapped[str | None] = mapped_column(Text)
    tools: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredient"
    recipe_ingredient_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.recipe_id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.ingredient_id"), index=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(Text)
    is_optional: Mapped[bool] = mapped_column(Boolean, server_default="false")


class RecipeDiet(Base):
    __tablename__ = "recipe_diet"
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.recipe_id", ondelete="CASCADE"), primary_key=True)
    preference_id: Mapped[int] = mapped_column(
        ForeignKey("preference.preference_id", ondelete="CASCADE"), primary_key=True)


class BookmarkedRecipe(Base):
    __tablename__ = "bookmarked_recipe"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.recipe_id", ondelete="CASCADE"), primary_key=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, server_default="false")
    bookmarked_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_item"
    __table_args__ = (
        CheckConstraint("status IN ('pending','purchased')"),
        Index("ix_shopping_user_ingredient", "user_id", "ingredient_id"),
    )
    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.ingredient_id"))
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(Text)
    source_recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipe.recipe_id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
