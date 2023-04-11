"""
With thanks to
https://github.com/richardschwabe/discord-bot-2022-course/blob/main/pagination.py
"""
from typing import Union

import discord
from discord import Interaction, Message
from discord.ext.commands import Context
from discord.ui.view import View


class PaginationView(View):
    current_page: int = 1
    message: Message

    def __init__(self,
                 title: str,
                 fields: list[dict[str, str]],
                 show_page_count: bool = True,
                 fields_per_page: int = 5):
        """Constructor for PaginationView"""
        super().__init__(timeout=10 * 60)  # in seconds (so, 10 minutes)

        self.data = []
        for item in fields:
            for (key, value) in item.items():
                self.data.append({
                    "label": key,
                    "item": value
                })
        # print(f"__init__: {repr(self.data)}")
        self.title = title
        self.show_page_count = show_page_count
        self.fields_per_page = fields_per_page

    async def send(self, ctx: Union[Context, Interaction]):
        if isinstance(ctx, Context):
            message = await ctx.send(view=self)
        else:
            message = await ctx.edit_original_response(view=self)
        self.message = message
        await self.update_message(self.data[:self.fields_per_page])

    def create_embed(self, data):
        title = self.title
        if self.show_page_count:
            title += f" {self.current_page} / {(int(len(self.data) / self.fields_per_page) + 1)}"
        print(f"create_embed: {self.current_page=}, {title=}")
        embed = discord.Embed(title=title)
        for field in data:
            embed.add_field(name=field['label'], value=field['item'], inline=True)
            print(f"create_embed: {repr(field)}")
        return embed

    async def update_message(self, data):
        self.update_buttons()
        await self.message.edit(embed=self.create_embed(data), view=self)

    def update_buttons(self):
        if self.current_page == 1:
            self.first_page_button.disabled = True
            self.prev_button.disabled = True
            self.first_page_button.style = discord.ButtonStyle.gray
            self.prev_button.style = discord.ButtonStyle.gray
        else:
            self.first_page_button.disabled = False
            self.prev_button.disabled = False
            self.first_page_button.style = discord.ButtonStyle.green
            self.prev_button.style = discord.ButtonStyle.primary

        if self.current_page == int(len(self.data) / self.fields_per_page) + 1:
            self.next_button.disabled = True
            self.last_page_button.disabled = True
            self.last_page_button.style = discord.ButtonStyle.gray
            self.next_button.style = discord.ButtonStyle.gray
        else:
            self.next_button.disabled = False
            self.last_page_button.disabled = False
            self.last_page_button.style = discord.ButtonStyle.green
            self.next_button.style = discord.ButtonStyle.primary

    def get_current_page_data(self):
        until_item = self.current_page * self.fields_per_page
        from_item = until_item - self.fields_per_page
        return self.data[from_item:until_item]

    @discord.ui.button(label="|<",
                       style=discord.ButtonStyle.green)
    async def first_page_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = 1

        await self.update_message(self.get_current_page_data())

    @discord.ui.button(label="<",
                       style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message(self.get_current_page_data())

    @discord.ui.button(label=">",
                       style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message(self.get_current_page_data())

    @discord.ui.button(label=">|",
                       style=discord.ButtonStyle.green)
    async def last_page_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        self.current_page = int(len(self.data) / self.fields_per_page) + 1
        await self.update_message(self.get_current_page_data())
