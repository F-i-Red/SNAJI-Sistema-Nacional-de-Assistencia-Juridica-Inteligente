
export class SessionManager {

  static storeToken(token: string) {

    localStorage.setItem("snaji_token", token);
  }

  static getToken() {

    return localStorage.getItem("snaji_token");
  }
}
