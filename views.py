import discord

class SignUpView(discord.ui.View):
    @discord.ui.button(label="Sign Up")
    async def sign_up(self, interaction, button):
        print("Someone signed up!")
        await interaction.response.defer()

    @discord.ui.button(label="Cancel")
    async def cancel(self, interaction, button):
        print("Someone cancelled!")
        await interaction.response.defer()
