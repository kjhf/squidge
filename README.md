# squidge
Cleanup bot bridge project for mediawiki and discord, for squidging vandal grime and auto-improving wikis.
Code on [GitHub](https://github.com/kjhf/squidge).

## Requirements
- A [Discord Dev account](https://discord.com/developers/applications)
- Python 3.9+ and pip
- Python requirements found in the [usual place](requirements.txt).
  - `pip install -r .\requirements.txt`

## Bot Setup
* Copy the [.env file example](.env.example) to `.env` and fill in the values.
The comments should explain how to fill in the values.
* The Wiki permissions text channel should contain a message in the following JSON format:
```json
{
  "owner": [
    "97288493029416960"
  ],
  "admin": [],
  "editor": [],
  "patrol": [
    "97288493029416960"
  ]
}
```
where the owner id is your Discord id.

Owner is bot owner and highest privilege. Owner(s) may assign new user ids.

Admin are power users that can do anything to the wiki that the bot has permissions for. Admins cannot change uesr ids.

Editors are users that may use the bot but some functionality is restricted.

Patrol are users that will get pinged if potential vandalism is detected. 

## Contributing
* See [project notes](NOTES.md) for potential implementation and TODOs.
* Please start a branch and make a pull request into main when implementing a small and reviewable piece of work.
