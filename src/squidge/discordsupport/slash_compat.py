from discord.ext.commands import Context


async def defer_if_interaction(ctx: Context):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)


async def send_or_edit(ctx: Context, message: str):
    if ctx.interaction:
        await ctx.interaction.edit_original_response(content=message)
    else:
        await ctx.send(content=message)
