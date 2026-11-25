interface Window {
  UniSpaceI18n: {
    languages: string[];
    register(lang: string, entries: Record<string, string>): void;
    current(): string;
    setLanguage(lang: string): void;
    t(key: string, vars?: Record<string, string | number>): string;
    apply(root?: ParentNode): void;
  };
  UniSpaceApi: {
    faculties(): Promise<any[]>;
    groups(facultyId: string): Promise<any[]>;
    professors(facultyId: string): Promise<any[]>;
    classrooms(facultyId?: string): Promise<any[]>;
    freeClassrooms(params: Record<string, any>): Promise<any[]>;
    schedule(params: Record<string, any>): Promise<any>;
    saveStudyProfile(facultyId: string, formationId: string): Promise<any>;
    createBooking(body: Record<string, any>): Promise<any>;
    myBookings(): Promise<any[]>;
    cancelBooking(id: string): Promise<any>;
    pendingBookings(): Promise<any[]>;
    decideBooking(id: string, body: Record<string, any>): Promise<any>;
    adminBookings(params?: Record<string, any>): Promise<{
      items: any[];
      total: number;
      limit: number;
      offset: number;
    }>;
    adminCancelBooking(id: string, body?: Record<string, any>): Promise<any>;
    adminClassrooms(facultyId?: string): Promise<any[]>;
    patchAdminClassroom(id: string, body: Record<string, any>): Promise<any>;
  };
  UniSpaceAuth: {
    ready: Promise<any>;
    user(): any;
    roleLabel(role: string): string;
    isAdmin(): boolean;
    logout(): Promise<void>;
  };
  UniSpaceBookings: {
    link(params: Record<string, any>): string;
    readPrefill(search: string): Record<string, any>;
    statusInfo(status: string): { key: string; pill: string };
    canCancel(booking: any): boolean;
  };
  UniSpaceGrid: {
    render(
      container: HTMLElement,
      items: any[],
      onSelect?: (item: any) => void,
      freeSlots?: any[],
    ): HTMLElement;
    toMinutes(hhmm: string): number;
  };
  UniSpaceModules: {
    list: Array<{
      number: number;
      startMin: number;
      endMin: number;
      start: string;
      end: string;
    }>;
    clock(min: number): string;
    endMin: number;
    end: string;
  };
  UniSpaceUI: Record<string, any>;
}
