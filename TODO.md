# TODO's

## Fix

- Fix Frontend: Polls, small buttons, button states sync between items, etc.
- Fix Health Check: Configure WILDDUCK In gobal Systems Settings (Tenant Independent) and make sure it works with the new tenant middleware.
- Fix Frontend: Tabs / Titles. Make a global Title. Tabs should not have a subtitle, as tab already gives the title / context. Tabs should not have a title, as the title is already given by the page / tab group.

## Feat

- Feat: Change Log Page
- Feat: Add Tenant Middleware to all API Routes
- Feat: Global User Settings: Add a global user settings page to manage user settings that are not tenant specific (e.g. email, password, etc.)
- Feat: Add a global settings page to manage global settings that are not tenant specific (e.g. email, password, etc.)
- Feat Global User Login / Verification / Logout: Add a global user login / verification / logout system that is not tenant specific (e.g. email, password, etc.)
- Feat Extend Inventory, Tenant Inventory System for Items, Tools, Machines, but also Furniture, Keys, etc. (e.g. for a Makerspace, Hackerspace, etc.). Let me assign items to Members
  - Display In the frontend in Tabs or any other way. Like Items / Machines / Tools Inventory, Room / General Inventory (Furniture), Keys Inventory
  - Insctructions is only needed for Items, Machines and Tools. For Furniture and Keys, no instructions are needed. But maybe a description is needed for Furniture and Keys.
  - For Keys we need to be able to assign them to members, and add a serial number to the key.
  - Add an optional serial number to the item, machine or tool.
- Feat Members of a tenant link to a global user. All changes like mail, password, etc. are done in the global user settings. The tenant member is just a link to the global user. The global user can be a member of multiple tenants.
  - Allow custom per tenant settings for the global user. For example, a global user can have different roles in different tenants. A global user can be an admin in one tenant and a member in another tenant.
  - Allow custom per tenant profile settings for the global user. For example, a global user can have different profile settings in different tenants. A global user can have a different profile picture in one tenant and a different profile picture in another tenant.
  - Member Mail address generation is handeled in the backend per tenant. The fronted / Member model should just have a username field. The backend will generate the mail address based on the tenant settings and the username. For example, if the tenant has a mail domain of "example.com" and the username is "john", the generated mail address will be "john@example.com"
  - The backend will also check if the generated mail address is unique within the tenant. If it is not unique, the backend will return an error and the frontend will display an error message to the user. The user can then choose a different username or contact the tenant admin to resolve the issue.
